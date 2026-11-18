"""
Email Verification Service with Multi-MX, Deliverability Signals, and Simultaneous Multi-Verification (up to 30 emails).
Fulfills Part 6, Part 11.5, Part 14, and Phase 1 enhancements.
"""
import re
import datetime
import concurrent.futures
from django.utils import timezone
from django.conf import settings
from core.utilities.constants import (
    STATUS_DELIVERABLE,
    STATUS_UNDELIVERABLE,
    STATUS_RISKY,
    STATUS_UNKNOWN,
)
from core.email_engine.syntax import validate_email_syntax
from core.email_engine.dns_checker import check_domain_dns
from core.email_engine.smtp_client import probe_smtp_multi_mx
from core.email_engine.catch_all import probe_catch_all
from core.email_engine.rules import evaluate_verification_rules, VerificationDecision
from apps.email_verifier.models import DomainRecord, EmailVerification
from apps.admin_management.models import is_suppressed_target
from apps.api_management.models import UsageRecord


def extract_emails_from_text(raw_text: str) -> list[str]:
    """
    Parses and extracts unique email addresses from free-form text input
    (separated by newlines, commas, semicolons, tabs, or spaces).
    Preserves original input ordering.
    """
    if not raw_text:
        return []

    tokens = re.split(r'[\r\n,;\s]+', raw_text.strip())
    seen = set()
    emails = []
    for t in tokens:
        clean = t.strip().strip("<>\"'()")
        if clean and "@" in clean:
            clean_lower = clean.lower()
            if clean_lower not in seen:
                seen.add(clean_lower)
                emails.append(clean)
    return emails


def get_or_refresh_domain_record(domain: str, dns_timeout: float = 5.0) -> tuple[DomainRecord, dict]:
    """Retrieves cached domain record or performs DNS lookup and saves cache."""
    now = timezone.now()
    existing = DomainRecord.objects.filter(domain=domain, expires_at__gt=now).first()
    if existing:
        return existing, {}

    # Perform DNS Check
    dns_res = check_domain_dns(domain, timeout=dns_timeout)
    expires = now + datetime.timedelta(hours=24)

    record, _ = DomainRecord.objects.update_or_create(
        domain=domain,
        defaults={
            "has_mx": dns_res.has_mx,
            "mx_hosts": [{"preference": p[0], "exchange": p[1]} for p in dns_res.mx_hosts],
            "has_address_fallback": dns_res.has_address_fallback,
            "expires_at": expires,
        }
    )
    dns_extra = {
        "has_spf": dns_res.has_spf,
        "has_dmarc": dns_res.has_dmarc,
        "spf_record": dns_res.spf_record,
        "dmarc_record": dns_res.dmarc_record,
    }
    return record, dns_extra


def probe_email_deliverability(
    raw_email: str,
    allow_smtp_probe: bool = True,
    is_suppressed: bool = False
) -> dict:
    """
    Executes DNS, multi-MX SMTP probing, catch-all checks, and 13 decision rules
    without writing to the database. Thread-safe for simultaneous execution in worker pools.
    """
    # 1. Syntax & Normalization
    syntax_res = validate_email_syntax(raw_email)
    normalized_email = syntax_res.normalized_email or raw_email.strip().lower()
    local_part = syntax_res.local_part
    domain = syntax_res.ascii_domain

    dns_temp_failure = False
    domain_exists = False
    has_mx_or_fallback = False
    mx_hosts_list: list[str] = []
    dns_signals = {}
    dns_mx_tuples = []
    dns_has_fallback = False
    dns_res = None

    if syntax_res.is_valid and domain:
        dns_res = check_domain_dns(domain)
        dns_temp_failure = dns_res.is_temporary_failure
        domain_exists = dns_res.domain_exists
        has_mx_or_fallback = dns_res.has_mx or dns_res.has_address_fallback
        if dns_res.mx_hosts:
            mx_hosts_list = [h[1] for h in dns_res.mx_hosts]
            dns_mx_tuples = [{"preference": p[0], "exchange": p[1]} for p in dns_res.mx_hosts]
        dns_has_fallback = dns_res.has_address_fallback

        dns_signals = {
            "has_spf": dns_res.has_spf,
            "has_dmarc": dns_res.has_dmarc,
            "spf_record": dns_res.spf_record,
            "dmarc_record": dns_res.dmarc_record,
        }

    # 2. Multi-MX SMTP Probing
    can_probe = getattr(settings, "SMTP_PROBING_ENABLED", False) and allow_smtp_probe and bool(mx_hosts_list)
    smtp_attempted = False
    smtp_timeout = False
    smtp_rejected = False
    smtp_policy_blocked = False
    smtp_temporary_failure = False
    smtp_greylisted = False
    smtp_accepted = False
    connected_mx = ""
    smtp_latency_ms = 0
    catch_all_state = "unknown"

    if can_probe:
        smtp_attempted = True
        helo = getattr(settings, "SMTP_PROBE_HELO", "mail.emailintelligence.local")
        mail_from = getattr(settings, "SMTP_PROBE_MAIL_FROM", "verify@emailintelligence.local")

        # Multi-MX failover probe
        probe_res = probe_smtp_multi_mx(
            mx_hosts=mx_hosts_list,
            target_email=normalized_email,
            helo_domain=helo,
            mail_from=mail_from,
        )

        smtp_timeout = probe_res.is_timeout
        smtp_rejected = probe_res.rejected
        smtp_policy_blocked = probe_res.is_policy_blocked
        smtp_temporary_failure = probe_res.is_temporary_failure
        smtp_greylisted = probe_res.is_greylisted
        smtp_accepted = probe_res.accepted
        connected_mx = probe_res.connected_mx
        smtp_latency_ms = probe_res.latency_ms

        # Catch-all probe if recipient accepted
        if smtp_accepted and connected_mx:
            ca_state, ca_probe = probe_catch_all(
                mx_host=connected_mx,
                domain=domain,
                helo_domain=helo,
                mail_from=mail_from,
            )
            catch_all_state = ca_state

    # 3. Evaluate 13 decision rules in order
    extra_evidence = {
        "syntax_valid": syntax_res.is_valid,
        "domain_exists": domain_exists,
        "mx_present": has_mx_or_fallback,
        "mx_hosts": mx_hosts_list[:3],
        "connected_mx": connected_mx,
        "smtp_latency_ms": smtp_latency_ms,
        "smtp_attempted": smtp_attempted,
        "smtp_accepted": smtp_accepted,
        "smtp_rejected": smtp_rejected,
        "catch_all_state": catch_all_state,
        "dns_signals": dns_signals,
    }

    decision: VerificationDecision = evaluate_verification_rules(
        is_suppressed=is_suppressed,
        syntax_valid=syntax_res.is_valid,
        domain_exists=domain_exists,
        dns_temporary_failure=dns_temp_failure,
        has_mx_or_fallback=has_mx_or_fallback,
        smtp_probing_enabled=can_probe,
        smtp_attempted=smtp_attempted,
        smtp_timeout=smtp_timeout,
        smtp_rejected=smtp_rejected,
        smtp_policy_blocked=smtp_policy_blocked,
        smtp_temporary_failure=smtp_temporary_failure,
        smtp_greylisted=smtp_greylisted,
        smtp_accepted=smtp_accepted,
        catch_all_state=catch_all_state,
        domain=domain,
        local_part=local_part,
        extra_evidence=extra_evidence,
    )

    return {
        "raw_email": raw_email,
        "normalized_email": normalized_email,
        "local_part": local_part,
        "domain": domain,
        "dns_res": dns_res,
        "decision": decision,
        "has_mx": bool(mx_hosts_list),
        "mx_hosts_tuples": dns_mx_tuples,
        "has_address_fallback": dns_has_fallback,
        "catch_all_state": catch_all_state,
    }


def save_verification_result(
    probe_dict: dict,
    owner,
    bulk_record_id=None,
    discovered_email_id=None,
    api_key=None,
) -> EmailVerification:
    """
    Safely persists DomainRecord, EmailVerification, and UsageRecord in the main thread.
    """
    domain = probe_dict.get("domain")
    domain_rec = None

    if domain and probe_dict.get("dns_res"):
        now = timezone.now()
        domain_rec = DomainRecord.objects.filter(domain=domain, expires_at__gt=now).first()
        if not domain_rec:
            expires = now + datetime.timedelta(hours=24)
            domain_rec, _ = DomainRecord.objects.update_or_create(
                domain=domain,
                defaults={
                    "has_mx": probe_dict["has_mx"],
                    "mx_hosts": probe_dict["mx_hosts_tuples"],
                    "has_address_fallback": probe_dict["has_address_fallback"],
                    "catch_all_state": probe_dict["catch_all_state"],
                    "expires_at": expires,
                }
            )
        elif probe_dict["catch_all_state"] != "unknown" and domain_rec.catch_all_state != probe_dict["catch_all_state"]:
            domain_rec.catch_all_state = probe_dict["catch_all_state"]
            domain_rec.save(update_fields=["catch_all_state"])

    decision = probe_dict["decision"]

    verification = EmailVerification.objects.create(
        owner=owner,
        email_normalized=probe_dict["normalized_email"],
        status=decision.status,
        reason_codes=decision.reason_codes,
        evidence_json=decision.evidence,
        domain_record=domain_rec,
        bulk_record_id=bulk_record_id,
        discovered_email_id=discovered_email_id,
        engine_version="1.1.0"
    )

    UsageRecord.objects.create(
        owner=owner,
        api_key=api_key,
        kind="verify_single",
        quantity=1
    )

    return verification


def verify_single_email(
    raw_email: str,
    owner,
    allow_smtp_probe: bool = False,
    discovered_email_id=None,
    bulk_record_id=None,
    api_key=None
) -> EmailVerification:
    """
    Executes full email verification pipeline per Part 6.2 and 6.4:
    Multi-MX probing, SPF/DMARC detection, catch-all checks, and strict 13 decision rules.
    """
    syntax_res = validate_email_syntax(raw_email)
    normalized = syntax_res.normalized_email or raw_email.strip().lower()
    is_suppressed = is_suppressed_target(normalized)

    probe_dict = probe_email_deliverability(
        raw_email=raw_email,
        allow_smtp_probe=allow_smtp_probe,
        is_suppressed=is_suppressed
    )

    return save_verification_result(
        probe_dict=probe_dict,
        owner=owner,
        bulk_record_id=bulk_record_id,
        discovered_email_id=discovered_email_id,
        api_key=api_key
    )


def verify_multiple_emails_concurrently(
    emails: list[str],
    owner,
    allow_smtp_probe: bool = True
) -> list[EmailVerification]:
    """
    Verifies up to 30 email addresses simultaneously in a single operation.
    Network and SMTP checks run concurrently across worker threads,
    and results are safely persisted to the database.
    """
    if not emails:
        return []

    # Limit to at most 30 emails
    targets = emails[:30]

    # Pre-check suppression for all targets
    suppressed_map = {e: is_suppressed_target(e.strip().lower()) for e in targets}

    def _worker(email_str: str):
        is_sup = suppressed_map.get(email_str, False)
        return email_str, probe_email_deliverability(
            raw_email=email_str,
            allow_smtp_probe=allow_smtp_probe,
            is_suppressed=is_sup
        )

    probe_results = {}
    max_workers = min(len(targets), 10)
    if max_workers > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_email = {executor.submit(_worker, em): em for em in targets}
            for future in concurrent.futures.as_completed(future_to_email):
                em, p_dict = future.result()
                probe_results[em] = p_dict
    else:
        for em in targets:
            _, p_dict = _worker(em)
            probe_results[em] = p_dict

    # Persist in the exact order of the original targets
    verifications = []
    for em in targets:
        p_dict = probe_results.get(em)
        if p_dict:
            ver = save_verification_result(
                probe_dict=p_dict,
                owner=owner
            )
            verifications.append(ver)

    return verifications

"""
Email Verification Decision Rules Evaluator.
Fulfills Part 6.3, Part 6.4 (Rules 1 to 13 evaluated in exact order), and Part 6.6.
"""
from typing import Any
from core.utilities.constants import (
    STATUS_DELIVERABLE,
    STATUS_UNDELIVERABLE,
    STATUS_RISKY,
    STATUS_UNKNOWN,
    EVIDENCE_NONE,
    EVIDENCE_SYNTAX,
    EVIDENCE_DOMAIN,
    EVIDENCE_MAILBOX,
    INVALID_SYNTAX,
    DOMAIN_NOT_FOUND,
    NO_MX_RECORDS,
    DNS_TEMPORARY_FAILURE,
    INSUFFICIENT_EVIDENCE,
    PROBE_UNAVAILABLE,
    SMTP_TIMEOUT,
    SMTP_REJECTION,
    PROVIDER_BLOCKED_PROBING,
    TEMPORARY_SERVER_FAILURE,
    GREYLISTED,
    CATCH_ALL_DOMAIN,
    SMTP_ACCEPTED,
    CATCH_ALL_NOT_DETERMINED,
    DISPOSABLE_ADDRESS,
    ROLE_BASED_ADDRESS,
    FREE_PROVIDER,
    SUPPRESSED_ADDRESS,
)
from core.email_engine.data_lists.disposable import is_disposable_domain
from core.email_engine.data_lists.free_providers import is_free_provider
from core.email_engine.data_lists.role_prefixes import is_role_based_localpart


class VerificationDecision:
    def __init__(
        self,
        status: str,
        reason_codes: list[str],
        evidence_level: str,
        evidence: dict[str, Any],
        is_role_based: bool,
        is_disposable: bool,
        is_free_provider: bool
    ):
        self.status = status
        self.reason_codes = reason_codes
        self.evidence_level = evidence_level
        self.evidence = evidence
        self.is_role_based = is_role_based
        self.is_disposable = is_disposable
        self.is_free_provider = is_free_provider

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reason_codes": self.reason_codes,
            "evidence_level": self.evidence_level,
            "evidence": self.evidence,
            "is_role_based": self.is_role_based,
            "is_disposable": self.is_disposable,
            "is_free_provider": self.is_free_provider,
        }


def evaluate_verification_rules(
    is_suppressed: bool,
    syntax_valid: bool,
    domain_exists: bool,
    dns_temporary_failure: bool,
    has_mx_or_fallback: bool,
    smtp_probing_enabled: bool,
    smtp_attempted: bool,
    smtp_timeout: bool,
    smtp_rejected: bool,
    smtp_policy_blocked: bool,
    smtp_temporary_failure: bool,
    smtp_greylisted: bool,
    smtp_accepted: bool,
    catch_all_state: str,  # 'yes', 'no', 'unknown'
    domain: str,
    local_part: str,
    extra_evidence: dict[str, Any] | None = None
) -> VerificationDecision:
    """
    Evaluates rules 1 to 13 in strict order per Part 6.4:
    Rules 1-12 give base status; Rule 13 is modifier; Informational flags added.
    """
    reason_codes: list[str] = []
    base_status: str = STATUS_UNKNOWN
    evidence_level: str = EVIDENCE_NONE
    evidence: dict[str, Any] = extra_evidence or {}

    # Check suppression first
    if is_suppressed:
        return VerificationDecision(
            status=STATUS_UNDELIVERABLE,
            reason_codes=[SUPPRESSED_ADDRESS],
            evidence_level=EVIDENCE_DOMAIN,
            evidence={"suppressed": True},
            is_role_based=is_role_based_localpart(local_part),
            is_disposable=is_disposable_domain(domain),
            is_free_provider=is_free_provider(domain),
        )

    # Rule 1: Syntax invalid
    if not syntax_valid:
        base_status = STATUS_UNDELIVERABLE
        reason_codes.append(INVALID_SYNTAX)
        evidence_level = EVIDENCE_SYNTAX

    # Rule 2: Domain does not exist (NXDOMAIN)
    elif not domain_exists and not dns_temporary_failure:
        base_status = STATUS_UNDELIVERABLE
        reason_codes.append(DOMAIN_NOT_FOUND)
        evidence_level = EVIDENCE_DOMAIN

    # Rule 3: Null MX declared or no MX and no address fallback
    elif not has_mx_or_fallback and not dns_temporary_failure:
        base_status = STATUS_UNDELIVERABLE
        reason_codes.append(NO_MX_RECORDS)
        evidence_level = EVIDENCE_DOMAIN

    # Rule 4: DNS timeout or server failure
    elif dns_temporary_failure:
        base_status = STATUS_UNKNOWN
        reason_codes.append(DNS_TEMPORARY_FAILURE)
        evidence_level = EVIDENCE_NONE

    # Rule 5: SMTP probing not performed (disabled, not permitted, or host cannot reach port 25)
    elif not smtp_probing_enabled or not smtp_attempted:
        base_status = STATUS_UNKNOWN
        reason_codes.extend([INSUFFICIENT_EVIDENCE, PROBE_UNAVAILABLE])
        evidence_level = EVIDENCE_DOMAIN

    # Rule 6: All MX connections time out or fail
    elif smtp_timeout:
        base_status = STATUS_UNKNOWN
        reason_codes.append(SMTP_TIMEOUT)
        evidence_level = EVIDENCE_DOMAIN

    # Rule 7: Recipient rejected with mailbox-nonexistent type response (permanent)
    elif smtp_rejected:
        base_status = STATUS_UNDELIVERABLE
        reason_codes.append(SMTP_REJECTION)
        evidence_level = EVIDENCE_MAILBOX

    # Rule 8: Rejection text indicates policy or reputation block
    elif smtp_policy_blocked:
        base_status = STATUS_UNKNOWN
        reason_codes.append(PROVIDER_BLOCKED_PROBING)
        evidence_level = EVIDENCE_DOMAIN

    # Rule 9: Temporary (4xx) response persisting after retries
    elif smtp_temporary_failure:
        base_status = STATUS_UNKNOWN
        reason_codes.append(GREYLISTED if smtp_greylisted else TEMPORARY_SERVER_FAILURE)
        evidence_level = EVIDENCE_DOMAIN

    # Rule 10: Recipient accepted and random-address probe also accepted (Catch-All)
    elif smtp_accepted and catch_all_state == "yes":
        base_status = STATUS_RISKY
        reason_codes.append(CATCH_ALL_DOMAIN)
        evidence_level = EVIDENCE_DOMAIN

    # Rule 11: Recipient accepted and random-address probe rejected (Definitive acceptance)
    elif smtp_accepted and catch_all_state == "no":
        base_status = STATUS_DELIVERABLE
        reason_codes.append(SMTP_ACCEPTED)
        evidence_level = EVIDENCE_MAILBOX

    # Rule 12: Recipient accepted but catch-all probe inconclusive
    elif smtp_accepted:
        base_status = STATUS_UNKNOWN
        reason_codes.append(CATCH_ALL_NOT_DETERMINED)
        evidence_level = EVIDENCE_DOMAIN

    else:
        # Fallback if no SMTP conditions matched
        base_status = STATUS_UNKNOWN
        reason_codes.append(INSUFFICIENT_EVIDENCE)
        evidence_level = EVIDENCE_DOMAIN

    # Rule 13: Modifier after rules 1 to 12
    # If disposable domain and base status is Deliverable or Unknown -> Risky
    is_disposable = is_disposable_domain(domain)
    if is_disposable:
        reason_codes.append(DISPOSABLE_ADDRESS)
        if base_status in (STATUS_DELIVERABLE, STATUS_UNKNOWN):
            base_status = STATUS_RISKY

    # Informational flags (do not change status)
    is_role = is_role_based_localpart(local_part)
    if is_role:
        reason_codes.append(ROLE_BASED_ADDRESS)

    is_free = is_free_provider(domain)
    if is_free:
        reason_codes.append(FREE_PROVIDER)

    return VerificationDecision(
        status=base_status,
        reason_codes=reason_codes,
        evidence_level=evidence_level,
        evidence=evidence,
        is_role_based=is_role,
        is_disposable=is_disposable,
        is_free_provider=is_free
    )


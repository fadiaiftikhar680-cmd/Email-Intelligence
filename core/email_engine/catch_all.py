"""
Catch-all Domain Detector.
Fulfills Part 6.1, Part 6.2 (Step 7), and Part 6.4 (Rules 10, 11, 12).
"""
import uuid
from core.email_engine.smtp_client import probe_smtp_recipient, SMTPProbeResult


def probe_catch_all(
    mx_host: str,
    domain: str,
    helo_domain: str = "mail.emailintelligence.local",
    mail_from: str = "verify@emailintelligence.local",
    timeout: float = 8.0,
    port: int = 25
) -> tuple[str, SMTPProbeResult]:
    """
    Probes a random, non-existent address on the domain.
    Returns (catch_all_state, probe_result) where catch_all_state is one of:
      - 'yes': server accepted arbitrary non-existent recipient -> Catch-all domain
      - 'no': server rejected arbitrary non-existent recipient -> Not a catch-all
      - 'unknown': probe timed out, failed or blocked
    """
    random_local = f"catchall_test_{uuid.uuid4().hex[:12]}"
    test_email = f"{random_local}@{domain}"

    probe_res = probe_smtp_recipient(
        mx_host=mx_host,
        target_email=test_email,
        helo_domain=helo_domain,
        mail_from=mail_from,
        timeout=timeout,
        port=port
    )

    if probe_res.accepted:
        return "yes", probe_res
    elif probe_res.rejected:
        return "no", probe_res
    else:
        return "unknown", probe_res


"""
Deterministic SMTP Client with Multi-MX Failover & Granular RFC 3463 Diagnostics.
Fulfills Part 6.1, Part 6.4 (Rules 6, 7, 8, 9, 10, 11), Part 22.1, and Part 23.5.
"""
import smtplib
import socket
import time
import logging
from core.utilities.constants import (
    DEFAULT_SMTP_TIMEOUT,
    SMTP_TIMEOUT,
    SMTP_REJECTION,
    PROVIDER_BLOCKED_PROBING,
    TEMPORARY_SERVER_FAILURE,
    GREYLISTED,
    SMTP_ACCEPTED,
)

logger = logging.getLogger(__name__)

# Keywords signaling anti-abuse / IP reputation / relay protection, NOT mailbox non-existence
POLICY_BLOCK_KEYWORDS = (
    "blocked", "blocklist", "blacklisted", "spam", "dnsbl", "spamhaus", "barracuda",
    "reputation", "policy", "denied", "access denied", "refused", "ip rate limit",
    "relay denied", "relay access denied", "not allowed", "administrative prohibition",
    "5.7.1", "5.7.0", "5.7.25", "dmarc", "spf check failed", "rbl"
)

# Keywords indicating explicit greylisting
GREYLIST_KEYWORDS = (
    "greylist", "graylist", "try again later", "deferred", "temporarily deferred",
    "4.7.1", "4.2.1"
)


class SMTPProbeResult:
    def __init__(
        self,
        attempted: bool = False,
        accepted: bool = False,
        rejected: bool = False,
        is_timeout: bool = False,
        is_policy_blocked: bool = False,
        is_temporary_failure: bool = False,
        is_greylisted: bool = False,
        reply_code: int = 0,
        reply_message: str = "",
        reason_code: str = "",
        connected_mx: str = "",
        latency_ms: int = 0,
    ):
        self.attempted = attempted
        self.accepted = accepted
        self.rejected = rejected
        self.is_timeout = is_timeout
        self.is_policy_blocked = is_policy_blocked
        self.is_temporary_failure = is_temporary_failure
        self.is_greylisted = is_greylisted
        self.reply_code = reply_code
        self.reply_message = reply_message
        self.reason_code = reason_code
        self.connected_mx = connected_mx
        self.latency_ms = latency_ms


def probe_single_host(
    mx_host: str,
    target_email: str,
    helo_domain: str,
    mail_from: str,
    timeout: float,
    port: int = 25
) -> SMTPProbeResult:
    """
    Executes RFC 5321 SMTP conversation with one host:
    CONNECT -> EHLO -> MAIL FROM -> RCPT TO -> QUIT
    Strictly NEVER sends DATA.
    """
    client = None
    start_time = time.time()
    try:
        client = smtplib.SMTP(timeout=timeout)
        code, resp = client.connect(mx_host, port)
        latency = int((time.time() - start_time) * 1000)

        # EHLO or HELO
        try:
            client.ehlo_or_helo_if_needed()
        except smtplib.SMTPException:
            pass

        # MAIL FROM
        code, resp = client.mail(mail_from)
        msg = resp.decode("utf-8", errors="ignore") if isinstance(resp, bytes) else str(resp)
        msg_lower = msg.lower()

        if code >= 400:
            if any(kw in msg_lower for kw in POLICY_BLOCK_KEYWORDS):
                return SMTPProbeResult(
                    attempted=True, is_policy_blocked=True, reply_code=code,
                    reply_message=msg, reason_code=PROVIDER_BLOCKED_PROBING,
                    connected_mx=mx_host, latency_ms=latency
                )
            is_grey = any(kw in msg_lower for kw in GREYLIST_KEYWORDS)
            return SMTPProbeResult(
                attempted=True, is_temporary_failure=(400 <= code < 500),
                is_greylisted=is_grey, reply_code=code, reply_message=msg,
                reason_code=GREYLISTED if is_grey else TEMPORARY_SERVER_FAILURE,
                connected_mx=mx_host, latency_ms=latency
            )

        # RCPT TO
        code, resp = client.rcpt(target_email)
        msg = resp.decode("utf-8", errors="ignore") if isinstance(resp, bytes) else str(resp)
        msg_lower = msg.lower()

        # Check for policy/reputation block
        if any(kw in msg_lower for kw in POLICY_BLOCK_KEYWORDS) or code in (554, 571):
            return SMTPProbeResult(
                attempted=True, is_policy_blocked=True, reply_code=code,
                reply_message=msg, reason_code=PROVIDER_BLOCKED_PROBING,
                connected_mx=mx_host, latency_ms=latency
            )

        # 250 / 251 -> Recipient accepted
        if 200 <= code < 300:
            return SMTPProbeResult(
                attempted=True, accepted=True, reply_code=code,
                reply_message=msg, reason_code=SMTP_ACCEPTED,
                connected_mx=mx_host, latency_ms=latency
            )

        # 4xx -> Temporary server failure / Greylisting
        if 400 <= code < 500:
            is_grey = any(kw in msg_lower for kw in GREYLIST_KEYWORDS)
            return SMTPProbeResult(
                attempted=True, is_temporary_failure=True, is_greylisted=is_grey,
                reply_code=code, reply_message=msg,
                reason_code=GREYLISTED if is_grey else TEMPORARY_SERVER_FAILURE,
                connected_mx=mx_host, latency_ms=latency
            )

        # 5xx (e.g. 550, 551, 553) -> Permanent mailbox nonexistent
        return SMTPProbeResult(
            attempted=True, rejected=True, reply_code=code,
            reply_message=msg, reason_code=SMTP_REJECTION,
            connected_mx=mx_host, latency_ms=latency
        )

    except (socket.timeout, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected):
        return SMTPProbeResult(
            attempted=True, is_timeout=True, reason_code=SMTP_TIMEOUT, connected_mx=mx_host
        )
    except (socket.error, smtplib.SMTPException) as e:
        err_str = str(e).lower()
        if "timeout" in err_str or "timed out" in err_str:
            return SMTPProbeResult(
                attempted=True, is_timeout=True, reason_code=SMTP_TIMEOUT, connected_mx=mx_host
            )
        return SMTPProbeResult(
            attempted=True, is_temporary_failure=True,
            reply_message=str(e), reason_code=TEMPORARY_SERVER_FAILURE,
            connected_mx=mx_host
        )
    finally:
        if client is not None:
            try:
                client.quit()
            except Exception:
                try:
                    client.close()
                except Exception:
                    pass


def probe_smtp_recipient(
    mx_host: str,
    target_email: str,
    helo_domain: str = "mail.emailintelligence.local",
    mail_from: str = "verify@emailintelligence.local",
    timeout: float = DEFAULT_SMTP_TIMEOUT,
    port: int = 25
) -> SMTPProbeResult:
    """Single host probe convenience wrapper."""
    return probe_single_host(mx_host, target_email, helo_domain, mail_from, timeout, port)


def probe_smtp_multi_mx(
    mx_hosts: list[str],
    target_email: str,
    helo_domain: str = "mail.emailintelligence.local",
    mail_from: str = "verify@emailintelligence.local",
    timeout: float = DEFAULT_SMTP_TIMEOUT,
    max_hosts_to_try: int = 3,
    port: int = 25
) -> SMTPProbeResult:
    """
    Tries up to max_hosts_to_try MX servers in priority order:
    If primary MX connection fails or times out, falls back sequentially to backup MX servers.
    """
    if not mx_hosts:
        return SMTPProbeResult(attempted=False, reason_code=SMTP_TIMEOUT)

    last_result = None
    for host in mx_hosts[:max_hosts_to_try]:
        res = probe_single_host(host, target_email, helo_domain, mail_from, timeout, port)
        last_result = res
        # If we got a definitive outcome (accepted, rejected, or policy blocked), do not retry secondary
        if res.accepted or res.rejected or res.is_policy_blocked:
            return res
        # If timeout or temporary failure, continue to next MX host in priority order

    return last_result or SMTPProbeResult(attempted=True, is_timeout=True, reason_code=SMTP_TIMEOUT)

"""
DNS, MX, SPF, and DMARC Records Checker using dnspython.
Fulfills Part 6.1, 6.2 (Step 3), 6.4 (Rules 2, 3, 4), and enhanced deliverability signals.
"""
import dns.resolver
import dns.exception
from core.utilities.constants import DEFAULT_DNS_TIMEOUT, DOMAIN_NOT_FOUND, NO_MX_RECORDS, DNS_TEMPORARY_FAILURE


class DNSCheckResult:
    def __init__(
        self,
        domain_exists: bool,
        has_mx: bool,
        mx_hosts: list[tuple[int, str]],
        has_address_fallback: bool = False,
        is_null_mx: bool = False,
        is_temporary_failure: bool = False,
        has_spf: bool = False,
        has_dmarc: bool = False,
        spf_record: str = "",
        dmarc_record: str = "",
        error_code: str | None = None,
        details: str = ""
    ):
        self.domain_exists = domain_exists
        self.has_mx = has_mx
        self.mx_hosts = mx_hosts
        self.has_address_fallback = has_address_fallback
        self.is_null_mx = is_null_mx
        self.is_temporary_failure = is_temporary_failure
        self.has_spf = has_spf
        self.has_dmarc = has_dmarc
        self.spf_record = spf_record
        self.dmarc_record = dmarc_record
        self.error_code = error_code
        self.details = details


def check_domain_dns(domain: str, timeout: float = DEFAULT_DNS_TIMEOUT) -> DNSCheckResult:
    """
    Performs DNS resolution for a domain:
    1. Checks if domain exists via SOA/A/MX lookup.
    2. Queries MX records and sorts by priority.
    3. Detects Null MX (RFC 7505).
    4. Checks A/AAAA address fallback if no MX is returned.
    5. Extracts SPF and DMARC authentication policies.
    """
    if not domain:
        return DNSCheckResult(False, False, [], error_code=DOMAIN_NOT_FOUND, details="Empty domain.")

    resolver = dns.resolver.Resolver()
    resolver.timeout = timeout
    resolver.lifetime = timeout

    # 1. Query MX records
    mx_hosts: list[tuple[int, str]] = []
    has_spf = False
    has_dmarc = False
    spf_record = ""
    dmarc_record = ""

    try:
        answers = resolver.resolve(domain, "MX")
        for rdata in answers:
            exchange = str(rdata.exchange).rstrip(".").lower()
            preference = int(rdata.preference)
            # RFC 7505 Null MX: preference 0 and exchange "." or empty
            if preference == 0 and (exchange == "" or exchange == "."):
                return DNSCheckResult(
                    domain_exists=True,
                    has_mx=False,
                    mx_hosts=[],
                    is_null_mx=True,
                    error_code=NO_MX_RECORDS,
                    details="RFC 7505 Null MX record declared (domain does not accept email)."
                )
            mx_hosts.append((preference, exchange))

        mx_hosts.sort(key=lambda x: x[0])

    except dns.resolver.NXDOMAIN:
        return DNSCheckResult(
            domain_exists=False,
            has_mx=False,
            mx_hosts=[],
            error_code=DOMAIN_NOT_FOUND,
            details="Domain does not exist (NXDOMAIN)."
        )
    except (dns.resolver.Timeout, dns.resolver.NoNameservers):
        return DNSCheckResult(
            domain_exists=False,
            has_mx=False,
            mx_hosts=[],
            is_temporary_failure=True,
            error_code=DNS_TEMPORARY_FAILURE,
            details="DNS query timed out or nameservers failed to respond."
        )
    except dns.resolver.NoAnswer:
        pass
    except dns.exception.DNSException as e:
        return DNSCheckResult(
            domain_exists=False,
            has_mx=False,
            mx_hosts=[],
            is_temporary_failure=True,
            error_code=DNS_TEMPORARY_FAILURE,
            details=f"DNS query error: {str(e)}"
        )

    # 2. Check SPF (TXT records on root domain)
    try:
        txt_records = resolver.resolve(domain, "TXT")
        for rdata in txt_records:
            txt_str = "".join([s.decode("utf-8", errors="ignore") if isinstance(s, bytes) else str(s) for s in rdata.strings])
            if txt_str.startswith("v=spf1"):
                has_spf = True
                spf_record = txt_str[:120]
                break
    except Exception:
        pass

    # 3. Check DMARC (TXT record on _dmarc.<domain>)
    try:
        dmarc_txt = resolver.resolve(f"_dmarc.{domain}", "TXT")
        for rdata in dmarc_txt:
            d_str = "".join([s.decode("utf-8", errors="ignore") if isinstance(s, bytes) else str(s) for s in rdata.strings])
            if d_str.startswith("v=DMARC1"):
                has_dmarc = True
                dmarc_record = d_str[:120]
                break
    except Exception:
        pass

    if mx_hosts:
        return DNSCheckResult(
            domain_exists=True,
            has_mx=True,
            mx_hosts=mx_hosts,
            has_address_fallback=False,
            has_spf=has_spf,
            has_dmarc=has_dmarc,
            spf_record=spf_record,
            dmarc_record=dmarc_record,
        )

    # 4. Check address fallback (A / AAAA)
    has_fallback = False
    try:
        try:
            resolver.resolve(domain, "A")
            has_fallback = True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            try:
                resolver.resolve(domain, "AAAA")
                has_fallback = True
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                has_fallback = False
    except (dns.resolver.Timeout, dns.resolver.NoNameservers):
        return DNSCheckResult(
            domain_exists=False,
            has_mx=False,
            mx_hosts=[],
            is_temporary_failure=True,
            error_code=DNS_TEMPORARY_FAILURE,
            details="DNS address fallback query timed out."
        )
    except Exception:
        has_fallback = False

    if has_fallback:
        return DNSCheckResult(
            domain_exists=True,
            has_mx=False,
            mx_hosts=[(0, domain.lower())],
            has_address_fallback=True,
            has_spf=has_spf,
            has_dmarc=has_dmarc,
            spf_record=spf_record,
            dmarc_record=dmarc_record,
        )

    return DNSCheckResult(
        domain_exists=True,
        has_mx=False,
        mx_hosts=[],
        has_address_fallback=False,
        has_spf=has_spf,
        has_dmarc=has_dmarc,
        spf_record=spf_record,
        dmarc_record=dmarc_record,
        error_code=NO_MX_RECORDS,
        details="No MX records and no A/AAAA address fallback found."
    )

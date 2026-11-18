"""
SSRF Protection and URL Safety Validation Module.
Fulfills Part 7.2, Part 8.3, and Phase 5 SSRF requirements.
"""
import ipaddress
import socket
import urllib.parse
from core.utilities.constants import UNSAFE_TARGET, INVALID_URL


# Disallowed IPv4 networks
DISALLOWED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),         # Broadcast/Current network
    ipaddress.ip_network("10.0.0.0/8"),        # RFC 1918 Private
    ipaddress.ip_network("100.64.0.0/10"),     # Shared address space / CGNAT
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / Cloud metadata (169.254.169.254)
    ipaddress.ip_network("172.16.0.0/12"),     # RFC 1918 Private
    ipaddress.ip_network("192.0.0.0/24"),      # IETF Protocol Assignments
    ipaddress.ip_network("192.0.2.0/24"),      # TEST-NET-1
    ipaddress.ip_network("192.168.0.0/16"),    # RFC 1918 Private
    ipaddress.ip_network("198.18.0.0/15"),     # Benchmark testing
    ipaddress.ip_network("198.51.100.0/24"),   # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),    # TEST-NET-3
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved / Future use
    ipaddress.ip_network("255.255.255.255/32"),# Broadcast
]

# Disallowed IPv6 networks
DISALLOWED_IPV6_NETWORKS = [
    ipaddress.ip_network("::/128"),            # Unspecified
    ipaddress.ip_network("::1/128"),           # Loopback
    ipaddress.ip_network("::ffff:0:0/96"),     # IPv4-mapped IPv6
    ipaddress.ip_network("100::/64"),          # Discard-only prefix
    ipaddress.ip_network("2001:db8::/32"),     # Documentation
    ipaddress.ip_network("fc00::/7"),          # Unique-local (ULA)
    ipaddress.ip_network("fe80::/10"),         # Link-local
    ipaddress.ip_network("ff00::/8"),          # Multicast
]


class SSRFValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def is_ip_disallowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Checks whether an IP address falls into any reserved, private, or loopback space."""
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        return True

    if isinstance(ip, ipaddress.IPv4Address):
        for net in DISALLOWED_IPV4_NETWORKS:
            if ip in net:
                return True
    elif isinstance(ip, ipaddress.IPv6Address):
        for net in DISALLOWED_IPV6_NETWORKS:
            if ip in net:
                return True

    return False


def validate_target_url(url_str: str, allowed_ports: tuple[int, ...] = (80, 443)) -> tuple[str, list[str]]:
    """
    Validates URL scheme, port, resolves host DNS, and blocks unsafe IPs.
    Returns (normalized_url, resolved_ip_list).
    Raises SSRFValidationError on any violation.
    """
    if not url_str or not isinstance(url_str, str):
        raise SSRFValidationError(INVALID_URL, "Target URL must be a non-empty string.")

    parsed = urllib.parse.urlsplit(url_str.strip())

    # 1. Enforce scheme: only http and https allowed
    if parsed.scheme.lower() not in ("http", "https"):
        raise SSRFValidationError(UNSAFE_TARGET, f"Scheme '{parsed.scheme}' is not allowed. Only HTTP/HTTPS permitted.")

    # 2. Extract host and port
    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError(INVALID_URL, "URL has no valid hostname.")

    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme.lower() == "https" else 80

    if port not in allowed_ports:
        raise SSRFValidationError(UNSAFE_TARGET, f"Port {port} is not in allowed target ports {allowed_ports}.")

    # 3. If hostname itself is directly an IP literal:
    try:
        direct_ip = ipaddress.ip_address(hostname.strip("[]"))
        if is_ip_disallowed(direct_ip):
            raise SSRFValidationError(UNSAFE_TARGET, f"IP address {hostname} belongs to a disallowed private/reserved range.")
        return url_str, [str(direct_ip)]
    except ValueError:
        pass  # Hostname is a domain name, proceed to DNS resolution

    # 4. Resolve DNS to check all returned IPs
    resolved_ips = []
    try:
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            ip_obj = ipaddress.ip_address(ip_str)
            if is_ip_disallowed(ip_obj):
                raise SSRFValidationError(UNSAFE_TARGET, f"Resolved address {ip_str} for host '{hostname}' is in a private/restricted network.")
            if ip_str not in resolved_ips:
                resolved_ips.append(ip_str)
    except socket.gaierror as e:
        raise SSRFValidationError(INVALID_URL, f"DNS resolution failed for '{hostname}': {e}")

    if not resolved_ips:
        raise SSRFValidationError(INVALID_URL, f"No IP addresses resolved for '{hostname}'.")

    return url_str, resolved_ips


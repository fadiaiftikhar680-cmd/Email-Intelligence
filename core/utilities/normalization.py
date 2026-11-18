"""
Normalization utilities for emails, URLs, and spreadsheet formula neutralization.
"""
import re
import urllib.parse
import idna


def normalize_email(email_str: str) -> tuple[str, str, str]:
    """
    Normalizes an email address according to Part 6.2 and Part 23.5:
    - Trims whitespace
    - Lowercases domain
    - Preserves local part
    - Converts IDN domain to ASCII (punycode) for DNS lookups
    Returns (normalized_full_email, local_part, ascii_domain).
    """
    if not email_str:
        return "", "", ""
    email_clean = str(email_str).strip()
    if "@" not in email_clean:
        return email_clean, email_clean, ""

    parts = email_clean.rsplit("@", 1)
    local_part = parts[0].strip()
    raw_domain = parts[1].strip().lower()

    # Convert IDN domain to ASCII
    try:
        ascii_domain = idna.encode(raw_domain).decode("ascii")
    except Exception:
        ascii_domain = raw_domain

    normalized_full = f"{local_part}@{ascii_domain}"
    return normalized_full, local_part, ascii_domain


def neutralize_formula_injection(val: str) -> str:
    """
    Part 8.4 & Part 23.5: Neutralize formula injection in CSV/XLSX export.
    If cell begins with =, +, -, @, prefix with a single quote.
    """
    if val is None:
        return ""
    val_str = str(val)
    if val_str and val_str[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val_str}"
    return val_str


def normalize_url(url_str: str) -> str:
    """
    Validates and normalizes target URL for safe crawler fetching.
    """
    if not url_str:
        return ""
    u = url_str.strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "https://" + u
    parsed = urllib.parse.urlsplit(u)
    normalized = urllib.parse.urlunsplit((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path or "/",
        parsed.query,
        ""  # drop fragment
    ))
    return normalized


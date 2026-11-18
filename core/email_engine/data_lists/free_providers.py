"""
Free consumer email providers data list.
Fulfills Part 6.1 and Part 6.4 (FREE_PROVIDER informational flag).
"""

FREE_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.fr",
    "hotmail.com", "hotmail.co.uk", "hotmail.fr", "outlook.com", "live.com",
    "msn.com", "aol.com", "icloud.com", "me.com", "mac.com", "mail.com",
    "gmx.com", "gmx.net", "zoho.com", "yandex.com", "yandex.ru", "proton.me",
    "protonmail.com", "tutanota.com", "tutamail.com", "fastmail.com",
    "hushmail.com", "inbox.com", "rediffmail.com", "lycos.com", "comcast.net",
    "sbcglobal.net", "att.net", "verizon.net", "cox.net", "charter.net"
}


def is_free_provider(domain: str) -> bool:
    if not domain:
        return False
    return domain.strip().lower() in FREE_PROVIDERS


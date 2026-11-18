"""
Role-based local part data list.
Fulfills Part 6.1 and Part 6.4 (ROLE_BASED_ADDRESS informational flag).
"""

ROLE_PREFIXES = {
    "admin", "administrator", "info", "information", "contact", "support",
    "help", "sales", "billing", "invoice", "finance", "accounting", "jobs",
    "careers", "recruiting", "hr", "humanresources", "team", "press",
    "media", "pr", "marketing", "office", "legal", "compliance", "security",
    "privacy", "postmaster", "hostmaster", "webmaster", "abuse", "root",
    "noc", "helpdesk", "service", "customerservice", "feedback", "inquiries",
    "enquiries", "orders", "tech", "operations", "ops", "hello", "hi"
}


def is_role_based_localpart(local_part: str) -> bool:
    if not local_part:
        return False
    lp = local_part.strip().lower()
    # Direct match or hyphen/dot separated prefix
    if lp in ROLE_PREFIXES:
        return True
    for delim in [".", "-", "_", "+"]:
        sub = lp.split(delim)[0]
        if sub in ROLE_PREFIXES:
            return True
    return False


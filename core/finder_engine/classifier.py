"""
Email Category Classifier.
Classifies emails based on local-part patterns and surrounding page context.
Fulfills Part 7.4.
"""
from core.utilities.constants import (
    CATEGORY_GENERAL,
    CATEGORY_SUPPORT,
    CATEGORY_SALES,
    CATEGORY_CAREERS,
    CATEGORY_HR,
    CATEGORY_MANAGEMENT,
    CATEGORY_PRESS,
    CATEGORY_OTHER,
    CATEGORY_UNKNOWN,
)

CATEGORY_RULES = {
    CATEGORY_SUPPORT: ["support", "help", "care", "service", "helpdesk", "tech", "customer"],
    CATEGORY_SALES: ["sales", "billing", "invoice", "orders", "pricing", "inquiries", "enquiries", "deals"],
    CATEGORY_CAREERS: ["jobs", "careers", "recruiting", "talent", "hiring", "work"],
    CATEGORY_HR: ["hr", "people", "humanresources"],
    CATEGORY_PRESS: ["press", "media", "pr", "news", "journalists", "communications"],
    CATEGORY_MANAGEMENT: ["ceo", "cto", "cfo", "founder", "executive", "board", "director", "leadership", "admin"],
    CATEGORY_GENERAL: ["info", "contact", "hello", "hi", "office", "team", "mail", "inbox"],
}


def classify_email_category(local_part: str, context_text: str = "") -> str:
    """
    Classifies an email local part into a category.
    Returns category string. Defaults to CATEGORY_GENERAL or CATEGORY_UNKNOWN.
    """
    if not local_part:
        return CATEGORY_UNKNOWN

    lp = local_part.lower().strip()
    # Check exact match or prefix
    for cat, keywords in CATEGORY_RULES.items():
        if lp in keywords:
            return cat
        for kw in keywords:
            if lp.startswith(kw) or f".{kw}" in lp or f"_{kw}" in lp or f"-{kw}" in lp:
                return cat

    if context_text:
        ctx = context_text.lower()
        for cat, keywords in CATEGORY_RULES.items():
            if any(kw in ctx for kw in keywords):
                return cat

    # If it looks like a personal name (e.g. john.doe, jsmith), classify as OTHER
    if "." in lp or "_" in lp or "-" in lp:
        return CATEGORY_OTHER

    return CATEGORY_UNKNOWN


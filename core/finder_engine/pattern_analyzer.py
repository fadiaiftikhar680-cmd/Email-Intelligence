"""
Company Email Pattern Analyzer and Inferred Candidate Generator.
Fulfills Part 7.5 (Method B) and Decision D-06 (Evidence Threshold).
"""
import re
from typing import NamedTuple


class PatternMatch(NamedTuple):
    pattern_name: str
    confidence_count: int
    sample_emails: list[str]


# Recognized patterns
PATTERNS = [
    ("{first}.{last}", r"^([a-z]+)\.([a-z]+)$"),
    ("{first}_{last}", r"^([a-z]+)_([a-z]+)$"),
    ("{first}{last}", r"^([a-z]+)([a-z]{3,})$"),  # heuristic
    ("{f}.{last}", r"^([a-z])\.([a-z]+)$"),
    ("{f}{last}", r"^([a-z])([a-z]{2,})$"),
    ("{first}.{l}", r"^([a-z]+)\.([a-z])$"),
    ("{first}{l}", r"^([a-z]{2,})([a-z])$"),
    ("{first}", r"^([a-z]{3,})$"),
]


def detect_company_email_pattern(discovered_emails: list[str]) -> PatternMatch | None:
    """
    Analyzes list of discovered email addresses on a domain.
    Requires at least 2 discovered emails consistent with the same pattern (Decision D-06 A).
    """
    if len(discovered_emails) < 2:
        return None

    pattern_counts: dict[str, list[str]] = {p[0]: [] for p in PATTERNS}

    for email in discovered_emails:
        if "@" not in email:
            continue
        local_part = email.split("@")[0].lower()

        # Test against patterns
        if "." in local_part:
            parts = local_part.split(".", 1)
            if len(parts[0]) == 1 and len(parts[1]) > 1:
                pattern_counts["{f}.{last}"].append(email)
            elif len(parts[0]) > 1 and len(parts[1]) == 1:
                pattern_counts["{first}.{l}"].append(email)
            elif len(parts[0]) > 1 and len(parts[1]) > 1:
                pattern_counts["{first}.{last}"].append(email)
        elif "_" in local_part:
            parts = local_part.split("_", 1)
            if len(parts[0]) > 1 and len(parts[1]) > 1:
                pattern_counts["{first}_{last}"].append(email)
        else:
            # Single string, could be {f}{last} or {first}
            if len(local_part) >= 3:
                pattern_counts["{f}{last}"].append(email)

    best_pattern = None
    max_count = 0
    for pat, matched_emails in pattern_counts.items():
        if len(matched_emails) >= 2 and len(matched_emails) > max_count:
            max_count = len(matched_emails)
            best_pattern = PatternMatch(pat, max_count, matched_emails)

    return best_pattern


def generate_inferred_candidate(
    full_name: str,
    domain: str,
    pattern: str
) -> str | None:
    """
    Generates an inferred candidate using a confirmed pattern.
    Output is strictly labeled 'inferred'.
    """
    if not full_name or not domain or not pattern:
        return None

    clean_name = re.sub(r"[^a-zA-Z\s]", "", full_name).strip().lower()
    name_parts = clean_name.split()
    if len(name_parts) < 2:
        first = name_parts[0] if name_parts else ""
        last = ""
    else:
        first = name_parts[0]
        last = name_parts[-1]

    if not first or not last:
        return None

    f = first[0]
    l = last[0]

    template_map = {
        "{first}.{last}": f"{first}.{last}",
        "{first}_{last}": f"{first}_{last}",
        "{f}.{last}": f"{f}.{last}",
        "{f}{last}": f"{f}{last}",
        "{first}.{l}": f"{first}.{l}",
        "{first}{l}": f"{first}{l}",
        "{first}": f"{first}",
    }

    local_part = template_map.get(pattern)
    if not local_part:
        return None

    return f"{local_part}@{domain.lower()}"


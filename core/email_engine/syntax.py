"""
Email Syntax Validation using email-validator and IDN support.
Fulfills Part 6.1, Part 6.2 (Step 1 & 2), and Part 23.5.
"""
from email_validator import validate_email, EmailNotValidError
from core.utilities.normalization import normalize_email


class SyntaxValidationResult:
    def __init__(self, is_valid: bool, normalized_email: str = "", local_part: str = "",
                 ascii_domain: str = "", error_message: str = ""):
        self.is_valid = is_valid
        self.normalized_email = normalized_email
        self.local_part = local_part
        self.ascii_domain = ascii_domain
        self.error_message = error_message


def validate_email_syntax(raw_email: str) -> SyntaxValidationResult:
    """
    Validates email syntax, parses IDN domains, and produces normalized forms.
    Does NOT check deliverability or query DNS (deliverability DNS is checked separately).
    """
    if not raw_email or not isinstance(raw_email, str):
        return SyntaxValidationResult(False, error_message="Empty email address.")

    clean_email = raw_email.strip()
    try:
        # check_deliverability=False because DNS is done in its own pipeline step with caching
        validated = validate_email(clean_email, check_deliverability=False)
        normalized = validated.normalized
        local_part = validated.local_part
        ascii_domain = validated.ascii_domain.lower() if validated.ascii_domain else validated.domain.lower()
        return SyntaxValidationResult(
            is_valid=True,
            normalized_email=f"{local_part}@{ascii_domain}",
            local_part=local_part,
            ascii_domain=ascii_domain
        )
    except EmailNotValidError as e:
        # Fallback to manual normalization for bad emails to record input
        norm_full, lp, dom = normalize_email(clean_email)
        return SyntaxValidationResult(
            is_valid=False,
            normalized_email=norm_full,
            local_part=lp,
            ascii_domain=dom,
            error_message=str(e)
        )


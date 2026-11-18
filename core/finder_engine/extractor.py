"""
HTML Extractor for Emails, Links, and Company Metadata.
Fulfills Part 7.4, Part 7.7, and high-accuracy business email discovery.
"""
import re
import urllib.parse
from bs4 import BeautifulSoup
from core.utilities.normalization import normalize_email
from core.finder_engine.classifier import classify_email_category

# Regex for finding email addresses in plain text
EMAIL_REGEX = re.compile(
    r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b",
    re.IGNORECASE
)

# Regex for common email obfuscations: e.g. "contact [at] company.com", "info(at)domain.com"
OBFUSCATED_EMAIL_REGEX = re.compile(
    r"\b([a-zA-Z0-9_.+-]+)\s*(?:\[at\]|\(at\)|\bat\b)\s*([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b",
    re.IGNORECASE
)

# Regex for phone numbers (North American and International)
PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
)

# File extensions that commonly get false-matched as emails (e.g. icon@2x.png)
INVALID_ASSET_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp", ".tiff",
    ".css", ".js", ".mjs", ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".mp4", ".mp3", ".webm", ".avi", ".mov", ".zip", ".tar", ".gz",
    ".pdf", ".json", ".xml", ".yaml", ".yml", ".map"
)

# Common dummy / template placeholder domains and local parts
DUMMY_DOMAINS = (
    "example.com", "example.org", "example.net", "domain.com", "email.com",
    "yourcompany.com", "yoursite.com", "mysite.com", "test.com", "sample.com",
    "w3.org", "schema.org", "sentry.io", "github.com", "gravatar.com"
)

DUMMY_LOCALPARTS = (
    "name", "user", "username", "email", "yourname", "first.last", "someone"
)

PRIORITY_KEYWORDS = [
    "contact", "about", "team", "people", "leadership",
    "support", "sales", "press", "help", "careers", "privacy"
]


class ExtractedEmail:
    def __init__(self, raw_email: str, normalized_email: str, local_part: str, domain: str, method: str, category: str, context: str = ""):
        self.raw_email = raw_email
        self.normalized_email = normalized_email
        self.local_part = local_part
        self.domain = domain
        self.method = method  # 'mailto_link', 'page_text', 'obfuscated_text', 'structured_data'
        self.category = category
        self.context = context


class ExtractedPageData:
    def __init__(
        self,
        emails: list[ExtractedEmail],
        internal_links: list[str],
        title: str = "",
        description: str = "",
        phones: list[str] = None,
        social_links: dict[str, str] = None,
        address: str = ""
    ):
        self.emails = emails
        self.internal_links = internal_links
        self.title = title
        self.description = description
        self.phones = phones or []
        self.social_links = social_links or {}
        self.address = address


def is_valid_discovered_email(email_str: str) -> bool:
    """Strictly validates whether an extracted token is a genuine business email."""
    if not email_str or "@" not in email_str:
        return False
    email_clean = email_str.strip().lower().rstrip(".,;:!?)")

    # Reject if ends with asset extension (e.g. icon@2x.png)
    if any(email_clean.endswith(ext) for ext in INVALID_ASSET_EXTENSIONS):
        return False

    parts = email_clean.split("@", 1)
    if len(parts) != 2:
        return False
    local_part, domain = parts[0], parts[1]

    # Validate local part
    if len(local_part) < 1 or len(local_part) > 64:
        return False
    if local_part in DUMMY_LOCALPARTS:
        return False

    # Validate domain
    if "." not in domain or len(domain) < 3:
        return False
    tld = domain.rsplit(".", 1)[-1]
    if len(tld) < 2 or not tld.isalpha():
        return False
    if domain in DUMMY_DOMAINS:
        return False

    return True


def extract_data_from_html(html_text: str, base_url: str, target_domain: str | None = None) -> ExtractedPageData:
    """
    Parses HTML content:
    - Extracts unique emails (mailto, visible text, obfuscated text, and JSON-LD).
    - Filters out false-positive image assets (e.g. @2x.png) and placeholders.
    - Extracts internal navigation links prioritized by contact/about keywords.
    - Extracts metadata: title, description, phones, and social profiles.
    """
    soup = BeautifulSoup(html_text, "html.parser")

    # Extract JSON-LD emails before decomposing scripts
    json_ld_emails = []
    for script_tag in soup.find_all("script", type="application/ld+json"):
        if script_tag.string:
            for match in EMAIL_REGEX.findall(script_tag.string):
                clean_match = match.strip().rstrip(".,;:!?)")
                if is_valid_discovered_email(clean_match):
                    json_ld_emails.append(clean_match)

    # Remove script and style elements
    for script_or_style in soup(["script", "style", "noscript", "svg"]):
        script_or_style.decompose()

    # Title & Meta Description
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    description = desc_tag.get("content", "").strip() if desc_tag else ""

    found_emails_dict: dict[str, ExtractedEmail] = {}

    def add_email(raw_target: str, method: str, context: str = ""):
        raw_clean = raw_target.strip().rstrip(".,;:!?)")
        if not is_valid_discovered_email(raw_clean):
            return
        norm_email, lp, dom = normalize_email(raw_clean)
        if norm_email and norm_email not in found_emails_dict:
            cat = classify_email_category(lp, context)
            found_emails_dict[norm_email] = ExtractedEmail(
                raw_email=raw_clean,
                normalized_email=norm_email,
                local_part=lp,
                domain=dom,
                method=method,
                category=cat,
                context=context[:100]
            )

    # 1. mailto: links (Highest reliability)
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if href.lower().startswith("mailto:"):
            raw_target = href[7:].split("?")[0].strip()
            add_email(raw_target, "mailto_link", a_tag.get_text(strip=True))

    # 2. JSON-LD structured data emails
    for em in json_ld_emails:
        add_email(em, "structured_data", "JSON-LD schema")

    # 3. Body visible text
    body_text = soup.get_text(separator=" ", strip=True)
    text_matches = EMAIL_REGEX.findall(body_text)
    for raw_target in text_matches:
        idx = body_text.find(raw_target)
        snippet = body_text[max(0, idx - 40): min(len(body_text), idx + len(raw_target) + 40)] if idx != -1 else ""
        add_email(raw_target, "page_text", snippet)

    # 4. Obfuscated emails: e.g. "contact [at] company.com"
    for m in OBFUSCATED_EMAIL_REGEX.finditer(body_text):
        obfuscated = f"{m.group(1)}@{m.group(2)}"
        add_email(obfuscated, "obfuscated_text", m.group(0))

    # 5. Phones
    phones = []
    for match in PHONE_REGEX.findall(body_text):
        match_clean = match.strip()
        if match_clean not in phones and len(phones) < 5:
            phones.append(match_clean)

    # 6. Social links & internal links
    base_parsed = urllib.parse.urlsplit(base_url)
    base_netloc = base_parsed.netloc.lower()

    social_links = {}
    internal_links = []
    seen_links = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        full_url = urllib.parse.urljoin(base_url, href)
        parsed_href = urllib.parse.urlsplit(full_url)
        href_netloc = parsed_href.netloc.lower()

        # Social links
        for platform in ["linkedin.com", "twitter.com", "x.com", "github.com", "facebook.com", "instagram.com"]:
            if platform in href_netloc and platform not in social_links:
                social_links[platform.split(".")[0]] = full_url

        # Internal links on same domain
        if href_netloc == base_netloc and full_url not in seen_links:
            if parsed_href.scheme in ("http", "https"):
                # Avoid non-HTML static file links
                path_lower = parsed_href.path.lower()
                if not any(path_lower.endswith(ext) for ext in INVALID_ASSET_EXTENSIONS):
                    seen_links.add(full_url)
                    internal_links.append(full_url)

    # Sort internal links so high-yield contact/about pages come first
    def priority_sort_key(url: str) -> int:
        u_lower = url.lower()
        for idx, kw in enumerate(PRIORITY_KEYWORDS):
            if kw in u_lower:
                return idx
        return len(PRIORITY_KEYWORDS) + 1

    internal_links.sort(key=priority_sort_key)

    return ExtractedPageData(
        emails=list(found_emails_dict.values()),
        internal_links=internal_links,
        title=title,
        description=description,
        phones=phones,
        social_links=social_links
    )

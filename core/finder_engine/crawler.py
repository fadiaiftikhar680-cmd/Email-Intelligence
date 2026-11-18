"""
Bounded Company Website Crawler.
Fulfills Part 7.3, Part 7.4, and Part 8.3 with high-yield priority crawling.
"""
import time
import urllib.parse
from core.finder_engine.safe_fetch import safe_fetch_url
from core.finder_engine.robots import check_robots_allowed
from core.finder_engine.extractor import extract_data_from_html, ExtractedEmail, ExtractedPageData
from core.utilities.constants import (
    DEFAULT_MAX_CRAWL_DEPTH,
    DEFAULT_MAX_CRAWL_PAGES,
    ACCESS_RESTRICTED,
    SITE_UNREACHABLE,
)


class CrawledPageRecord:
    def __init__(self, url: str, final_url: str, http_status: int, robots_allowed: bool,
                 content_hash: str = "", error_code: str | None = None):
        self.url = url
        self.final_url = final_url
        self.http_status = http_status
        self.robots_allowed = robots_allowed
        self.content_hash = content_hash
        self.error_code = error_code


class CrawlJobResult:
    def __init__(self, domain: str, visited_pages: list[CrawledPageRecord],
                 discovered_emails: list[ExtractedEmail], company_metadata: dict):
        self.domain = domain
        self.visited_pages = visited_pages
        self.discovered_emails = discovered_emails
        self.company_metadata = company_metadata


def crawl_company_website(
    start_url: str,
    max_depth: int = DEFAULT_MAX_CRAWL_DEPTH,
    max_pages: int = DEFAULT_MAX_CRAWL_PAGES,
    delay_between_requests: float = 0.0
) -> CrawlJobResult:
    """
    Crawls public pages of a website up to max_pages / max_depth:
    - Obeying robots.txt
    - Prioritizing high-yield business contact and team pages
    - Fast sub-second extraction without artificial delay
    - Extracting and deduplicating emails with method and source URL
    - Collecting company metadata (title, description, phone, social)
    """
    parsed_start = urllib.parse.urlsplit(start_url)
    origin = f"{parsed_start.scheme}://{parsed_start.netloc}"
    domain = parsed_start.netloc.lower()

    # Queue of (url, depth)
    queue: list[tuple[str, int]] = [(start_url, 0)]

    # Proactively seed queue with standard high-yield contact endpoints
    high_yield_paths = ["/contact", "/contact-us", "/about", "/about-us", "/team", "/privacy"]
    for path in high_yield_paths:
        queue.append((f"{origin}{path}", 1))

    visited_urls: set[str] = set()
    visited_records: list[CrawledPageRecord] = []
    discovered_emails_dict: dict[str, ExtractedEmail] = {}

    company_metadata = {
        "name": domain.split(".")[0].capitalize(),
        "domain": domain,
        "website": start_url,
        "title": "",
        "description": "",
        "phones": [],
        "social_links": {},
    }

    while queue and len(visited_records) < max_pages:
        current_url, depth = queue.pop(0)

        # Normalize URL to avoid duplicates with trailing slashes
        clean_url = current_url.split("#")[0].rstrip("/")
        if clean_url in visited_urls:
            continue
        visited_urls.add(clean_url)

        # 1. Check robots.txt (fast cached check)
        if not check_robots_allowed(current_url):
            visited_records.append(CrawledPageRecord(
                url=current_url,
                final_url=current_url,
                http_status=403,
                robots_allowed=False,
                error_code=ACCESS_RESTRICTED
            ))
            continue

        # Optional delay (default 0 for speed)
        if visited_records and delay_between_requests > 0:
            time.sleep(delay_between_requests)

        # 2. Fetch page safely
        fetch_res = safe_fetch_url(current_url)
        if not fetch_res.success or not fetch_res.content:
            visited_records.append(CrawledPageRecord(
                url=current_url,
                final_url=fetch_res.final_url or current_url,
                http_status=fetch_res.status_code or 0,
                robots_allowed=True,
                error_code=fetch_res.error_code or SITE_UNREACHABLE
            ))
            continue

        visited_records.append(CrawledPageRecord(
            url=current_url,
            final_url=fetch_res.final_url,
            http_status=fetch_res.status_code,
            robots_allowed=True,
            content_hash=str(hash(fetch_res.content))
        ))

        # 3. Extract emails & metadata
        extracted: ExtractedPageData = extract_data_from_html(fetch_res.content, fetch_res.final_url, domain)

        # Set company metadata from first / home page
        if not company_metadata["title"] and extracted.title:
            company_metadata["title"] = extracted.title
        if not company_metadata["description"] and extracted.description:
            company_metadata["description"] = extracted.description
        if extracted.phones:
            for p in extracted.phones:
                if p not in company_metadata["phones"]:
                    company_metadata["phones"].append(p)
        if extracted.social_links:
            company_metadata["social_links"].update(extracted.social_links)

        # Collect discovered emails
        for em in extracted.emails:
            if em.normalized_email not in discovered_emails_dict:
                discovered_emails_dict[em.normalized_email] = em

        # 4. Enqueue internal links if depth permits (prioritizing contact/about links)
        if depth < max_depth and len(visited_records) < max_pages:
            for next_link in extracted.internal_links:
                norm_next = next_link.split("#")[0].rstrip("/")
                if norm_next not in visited_urls and len(visited_records) + len(queue) < max_pages * 2:
                    queue.append((next_link, depth + 1))

    return CrawlJobResult(
        domain=domain,
        visited_pages=visited_records,
        discovered_emails=list(discovered_emails_dict.values()),
        company_metadata=company_metadata
    )

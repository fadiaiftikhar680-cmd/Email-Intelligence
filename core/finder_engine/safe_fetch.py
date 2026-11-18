"""
Safe Outbound HTTP Fetcher with SSRF validation and redirect guard.
Fulfills Part 7.2, Part 8.3, and Phase 5 requirements.
"""
import httpx
import logging
import urllib.parse
from core.security.ssrf import validate_target_url, SSRFValidationError
from core.utilities.constants import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_MAX_PAGE_RESPONSE_SIZE,
    UNSAFE_TARGET,
    SITE_UNREACHABLE,
    CRAWL_TIMEOUT,
)

logger = logging.getLogger(__name__)

USER_AGENT = "EmailIntelligencePlatformBot/1.0 (+https://emailintelligence.local/bot; public business email discovery)"


class SafeFetchResult:
    def __init__(
        self,
        success: bool,
        status_code: int = 0,
        content: str = "",
        final_url: str = "",
        content_type: str = "",
        error_code: str | None = None,
        error_message: str = ""
    ):
        self.success = success
        self.status_code = status_code
        self.content = content
        self.final_url = final_url
        self.content_type = content_type
        self.error_code = error_code
        self.error_message = error_message


def safe_fetch_url(
    target_url: str,
    max_redirects: int = 5,
    max_size_bytes: int = DEFAULT_MAX_PAGE_RESPONSE_SIZE,
    timeout_seconds: float = DEFAULT_READ_TIMEOUT
) -> SafeFetchResult:
    """
    Performs safe outbound HTTP GET request:
    1. Validates target URL against SSRF policy.
    2. Follows redirects manually, validating each hop.
    3. Enforces response size limit and skips non-text binaries.
    4. Handles connect/read timeouts safely.
    """
    current_url = target_url
    redirect_count = 0

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
        "Accept-Language": "en-US,en;q=0.8",
    }

    transport = httpx.HTTPTransport(retries=1)
    with httpx.Client(transport=transport, follow_redirects=False, timeout=timeout_seconds) as client:
        while True:
            # Step 1: Validate SSRF on current URL
            try:
                norm_url, _ = validate_target_url(current_url)
            except SSRFValidationError as e:
                return SafeFetchResult(
                    success=False,
                    final_url=current_url,
                    error_code=UNSAFE_TARGET,
                    error_message=f"SSRF validation failed: {e.message}"
                )

            # Step 2: Request hop
            try:
                response = client.get(norm_url, headers=headers)
            except httpx.TimeoutException:
                return SafeFetchResult(
                    success=False,
                    final_url=current_url,
                    error_code=CRAWL_TIMEOUT,
                    error_message="Connection or read timed out."
                )
            except httpx.RequestError as e:
                return SafeFetchResult(
                    success=False,
                    final_url=current_url,
                    error_code=SITE_UNREACHABLE,
                    error_message=f"Target site could not be reached: {str(e)}"
                )

            # Step 3: Handle Redirects
            if response.is_redirect:
                redirect_count += 1
                if redirect_count > max_redirects:
                    return SafeFetchResult(
                        success=False,
                        final_url=current_url,
                        error_code=SITE_UNREACHABLE,
                        error_message="Too many redirects encountered."
                    )
                location = response.headers.get("location")
                if not location:
                    break
                current_url = urllib.parse.urljoin(current_url, location)
                continue

            # Step 4: Validate Content-Type and Size
            content_type = response.headers.get("content-type", "").lower()
            if not any(t in content_type for t in ["text/html", "text/plain", "application/xhtml+xml"]):
                return SafeFetchResult(
                    success=False,
                    status_code=response.status_code,
                    final_url=str(response.url),
                    content_type=content_type,
                    error_code=UNSAFE_TARGET,
                    error_message=f"Disallowed content type: {content_type}"
                )

            content_bytes = response.content
            if len(content_bytes) > max_size_bytes:
                return SafeFetchResult(
                    success=False,
                    status_code=response.status_code,
                    final_url=str(response.url),
                    error_code=UNSAFE_TARGET,
                    error_message=f"Response exceeded size limit ({len(content_bytes)} > {max_size_bytes} bytes)."
                )

            text_content = response.text
            return SafeFetchResult(
                success=(200 <= response.status_code < 300),
                status_code=response.status_code,
                content=text_content,
                final_url=str(response.url),
                content_type=content_type
            )


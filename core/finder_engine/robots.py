"""
Robots.txt Parser and Access Rule Checker.
Fulfills Part 7.3 and Part 8.3.
"""
import urllib.robotparser
import urllib.parse
from core.finder_engine.safe_fetch import safe_fetch_url, USER_AGENT

_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


def check_robots_allowed(target_url: str) -> bool:
    """
    Checks if fetching target_url is allowed by the host's robots.txt.
    Returns True if allowed, False if disallowed.
    """
    if not target_url:
        return False

    parsed = urllib.parse.urlsplit(target_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    if origin in _robots_cache:
        rp = _robots_cache[origin]
        return rp.can_fetch(USER_AGENT, target_url)

    robots_url = f"{origin}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)

    fetch_res = safe_fetch_url(robots_url, timeout_seconds=4.0)
    if fetch_res.success and fetch_res.content:
        rp.parse(fetch_res.content.splitlines())
    else:
        # If no robots.txt or fetch failed (e.g. 404), allow crawling by default
        rp.allow_all = True

    _robots_cache[origin] = rp
    return rp.can_fetch(USER_AGENT, target_url)


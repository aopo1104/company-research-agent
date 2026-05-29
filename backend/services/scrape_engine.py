"""
Multi-strategy scrape engine inspired by CompetitiveAnalysis project.

Strategies (tried in order):
1. static-html: httpx GET + BeautifulSoup content extraction
2. json-ld: Extract structured data from script[type="application/ld+json"]
3. enhanced-static: httpx with anti-bot headers + content extraction
4. tavily-fallback: Tavily crawl/extract as final fallback

Each method returns a standardized result structure.
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# Noise patterns to remove from extracted text
BOILERPLATE_PATTERNS = [
    re.compile(r"skip to (content|main|navigation)", re.I),
    re.compile(r"cookie (policy|consent|banner|notice)", re.I),
    re.compile(r"privacy policy", re.I),
    re.compile(r"terms (of|and) (service|use)", re.I),
    re.compile(r"all rights reserved", re.I),
    re.compile(r"subscribe to (our|the) newsletter", re.I),
    re.compile(r"sign up for", re.I),
    re.compile(r"follow us on", re.I),
]

# Tags to remove entirely
NOISE_TAGS = [
    "script", "style", "noscript", "iframe", "svg",
    "nav", "footer", "header",
]

MAX_TEXT_LENGTH = 20000


class ScrapeResult:
    """Standardized scrape result."""

    def __init__(
        self,
        url: str,
        title: str = "",
        text: str = "",
        method: str = "unknown",
        success: bool = False,
        failure_reason: str = "",
    ):
        self.url = url
        self.title = title
        self.text = text
        self.method = method
        self.success = success
        self.failure_reason = failure_reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "raw_content": self.text,
            "method": self.method,
            "success": self.success,
        }


def _purify_content(soup: BeautifulSoup) -> str:
    """Extract main content from a BeautifulSoup document, removing noise."""
    # Remove noise tags
    for tag_name in NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove hidden elements
    for el in soup.find_all(attrs={"style": re.compile(r"display:\s*none", re.I)}):
        el.decompose()
    for el in soup.find_all(attrs={"hidden": True}):
        el.decompose()

    # Try to find main content area
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find("div", class_=re.compile(r"(content|main|body|article)", re.I))
        or soup.find("body")
    )

    if not main_content:
        main_content = soup

    # Get text
    text = main_content.get_text(separator="\n", strip=True)

    # Remove boilerplate lines
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if any(p.search(line) for p in BOILERPLATE_PATTERNS):
            continue
        # Skip very short lines that are likely nav items
        if len(line) < 3:
            continue
        clean_lines.append(line)

    result = "\n".join(clean_lines)

    # Truncate if too long
    if len(result) > MAX_TEXT_LENGTH:
        result = result[:MAX_TEXT_LENGTH]

    return result


def _extract_title(soup: BeautifulSoup) -> str:
    """Extract page title from multiple sources."""
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)
    elif soup.find("meta", attrs={"property": "og:title"}):
        title = soup.find("meta", attrs={"property": "og:title"}).get("content", "")
    return title


def _extract_json_ld(soup: BeautifulSoup) -> str:
    """Extract structured data from JSON-LD scripts."""
    json_ld_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    if not json_ld_scripts:
        return ""

    parts = []
    for script in json_ld_scripts:
        try:
            data = json.loads(script.string or "")
            if isinstance(data, list):
                for item in data:
                    parts.append(_flatten_json_ld(item))
            else:
                parts.append(_flatten_json_ld(data))
        except (json.JSONDecodeError, TypeError):
            continue

    return "\n".join(filter(None, parts))


def _flatten_json_ld(data: dict, prefix: str = "") -> str:
    """Flatten a JSON-LD object into readable text."""
    if not isinstance(data, dict):
        return str(data) if data else ""

    parts = []
    skip_keys = {"@context", "@id", "url", "image", "logo"}

    for key, value in data.items():
        if key in skip_keys:
            continue
        if key == "@type":
            parts.append(f"Type: {value}")
        elif isinstance(value, str) and value.strip():
            # Remove HTML tags from value
            clean_value = re.sub(r"<[^>]+>", " ", value).strip()
            clean_value = re.sub(r"\s+", " ", clean_value)
            if len(clean_value) > 5:
                parts.append(f"{key}: {clean_value[:2000]}")
        elif isinstance(value, (int, float)):
            parts.append(f"{key}: {value}")
        elif isinstance(value, dict):
            nested = _flatten_json_ld(value, f"{key}.")
            if nested:
                parts.append(nested)
        elif isinstance(value, list) and len(value) <= 20:
            for i, item in enumerate(value[:10]):
                if isinstance(item, dict):
                    nested = _flatten_json_ld(item, f"{key}[{i}].")
                    if nested:
                        parts.append(nested)
                elif isinstance(item, str) and item.strip():
                    parts.append(f"{key}: {item}")

    return "\n".join(parts)


def _discover_links(soup: BeautifulSoup, base_url: str, max_links: int = 50) -> List[str]:
    """Discover internal links from a page for crawling."""
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()
    found = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        # Only same-domain links
        if parsed.netloc.lower() != base_domain:
            continue

        # Clean URL (remove fragments and query)
        clean_url = parsed._replace(fragment="", query="").geturl()

        # Skip common noise URLs
        path_lower = parsed.path.lower()
        skip_extensions = (".jpg", ".png", ".gif", ".svg", ".css", ".js", ".pdf", ".zip")
        if any(path_lower.endswith(ext) for ext in skip_extensions):
            continue

        found.add(clean_url)
        if len(found) >= max_links:
            break

    return list(found)


async def _fetch_page(url: str, enhanced: bool = False) -> Optional[httpx.Response]:
    """Fetch a page with httpx."""
    headers = {"User-Agent": USER_AGENT}
    if enhanced:
        parsed = urlparse(url)
        headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": f"{parsed.scheme}://{parsed.netloc}/",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Dest": "document",
        })

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=20.0,
            verify=False,
        ) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp
            logger.debug(f"Fetch returned status {resp.status_code} for {url}")
            return None
    except Exception as e:
        logger.debug(f"Fetch failed for {url}: {e}")
        return None


async def scrape_static(url: str) -> ScrapeResult:
    """Strategy 1: Static HTML fetch + content purification."""
    resp = await _fetch_page(url, enhanced=False)
    if not resp:
        return ScrapeResult(url=url, method="static", failure_reason="HTTP fetch failed")

    soup = BeautifulSoup(resp.text, "html.parser")
    title = _extract_title(soup)
    text = _purify_content(soup)

    if len(text) < 50:
        return ScrapeResult(url=url, title=title, text=text, method="static",
                            failure_reason="Content too short after purification")

    return ScrapeResult(url=url, title=title, text=text, method="static", success=True)


async def scrape_json_ld(url: str) -> ScrapeResult:
    """Strategy 2: Extract JSON-LD structured data."""
    resp = await _fetch_page(url, enhanced=False)
    if not resp:
        return ScrapeResult(url=url, method="json-ld", failure_reason="HTTP fetch failed")

    soup = BeautifulSoup(resp.text, "html.parser")
    title = _extract_title(soup)
    json_ld_text = _extract_json_ld(soup)

    if len(json_ld_text) < 50:
        return ScrapeResult(url=url, title=title, method="json-ld",
                            failure_reason="No substantial JSON-LD found")

    return ScrapeResult(url=url, title=title, text=json_ld_text, method="json-ld", success=True)


async def scrape_enhanced(url: str) -> ScrapeResult:
    """Strategy 3: Enhanced static with anti-bot headers."""
    resp = await _fetch_page(url, enhanced=True)
    if not resp:
        return ScrapeResult(url=url, method="enhanced-static",
                            failure_reason="Enhanced fetch failed")

    soup = BeautifulSoup(resp.text, "html.parser")
    title = _extract_title(soup)
    text = _purify_content(soup)

    if len(text) < 50:
        return ScrapeResult(url=url, title=title, text=text, method="enhanced-static",
                            failure_reason="Content too short after purification")

    return ScrapeResult(url=url, title=title, text=text, method="enhanced-static", success=True)


async def scrape_single_url(url: str) -> ScrapeResult:
    """Try all strategies in order for a single URL, return first success."""
    strategies = [
        ("static", scrape_static),
        ("json-ld", scrape_json_ld),
        ("enhanced-static", scrape_enhanced),
    ]

    for name, strategy_fn in strategies:
        try:
            result = await strategy_fn(url)
            if result.success:
                logger.info(f"[{name}] Success for {url} ({len(result.text)} chars)")
                return result
        except Exception as e:
            logger.debug(f"[{name}] Exception for {url}: {e}")
            continue

    return ScrapeResult(
        url=url,
        method="all-failed",
        failure_reason="All scrape strategies failed",
    )


async def crawl_site(
    url: str,
    max_pages: int = 50,
    max_depth: int = 1,
) -> Dict[str, Dict[str, Any]]:
    """
    Crawl a website starting from the given URL.
    Returns a dict of {url: {raw_content, source, method}}.

    Tries custom scraping first. Returns whatever was successfully scraped.
    The caller (grounding.py) should fall back to Tavily for failures.
    """
    results: Dict[str, Dict[str, Any]] = {}
    visited: set = set()
    to_visit: List[str] = [url]

    # Fetch the seed page first
    seed_result = await scrape_single_url(url)
    visited.add(url)

    if seed_result.success:
        results[url] = {
            "raw_content": seed_result.text,
            "title": seed_result.title,
            "source": "company_website",
            "method": seed_result.method,
        }

        # Discover links from seed page
        resp = await _fetch_page(url)
        if resp and max_depth > 0:
            soup = BeautifulSoup(resp.text, "html.parser")
            discovered = _discover_links(soup, url, max_links=max_pages)
            to_visit.extend(discovered)

    # Crawl discovered pages concurrently
    remaining = [u for u in to_visit if u not in visited][:max_pages - 1]

    if remaining:
        semaphore = asyncio.Semaphore(5)

        async def _scrape_with_limit(page_url: str) -> Optional[ScrapeResult]:
            async with semaphore:
                return await scrape_single_url(page_url)

        tasks = [_scrape_with_limit(u) for u in remaining]
        page_results = await asyncio.gather(*tasks, return_exceptions=True)

        for page_url, result in zip(remaining, page_results):
            visited.add(page_url)
            if isinstance(result, Exception):
                continue
            if result and result.success:
                results[page_url] = {
                    "raw_content": result.text,
                    "title": result.title,
                    "source": "company_website",
                    "method": result.method,
                }

    logger.info(
        f"Custom crawl completed: {len(results)}/{len(visited)} pages extracted"
    )
    return results


async def extract_url_content(url: str) -> Optional[str]:
    """
    Extract content from a single URL using multi-strategy approach.
    Returns raw_content string or None if all strategies fail.
    Used by enricher.py as replacement for Tavily extract().
    """
    result = await scrape_single_url(url)
    if result.success:
        return result.text
    return None


async def extract_urls_batch(urls: List[str], concurrency: int = 5) -> Dict[str, str]:
    """
    Extract content from multiple URLs.
    Returns {url: raw_content} for successful extractions.
    """
    semaphore = asyncio.Semaphore(concurrency)
    results: Dict[str, str] = {}

    async def _extract(url: str):
        async with semaphore:
            content = await extract_url_content(url)
            if content:
                results[url] = content

    await asyncio.gather(*[_extract(u) for u in urls], return_exceptions=True)
    return results

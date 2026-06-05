"""
================================================================================
scrape_engine.py - 自研多策略网页爬虫
================================================================================
实现3层爬虫策略，用于获取网页内容

使用场景:
  1. 阶段1 (grounding): 官网抓取
  2. 阶段6 (enricher): 获取搜索结果的完整内容

爬虫策略 (按顺序尝试):
  ① static-html: httpx GET + BeautifulSoup 内容提取
                  适用: 大多数静态网站
                  速度: 快
                  
  ② json-ld: 解析 script[type="application/ld+json"] 结构化数据
             适用: 支持JSON-LD的现代网站
             精度: 高（结构化数据）
             
  ③ enhanced-static: httpx + User-Agent headers (模拟浏览器)
                      适用: 反爬虫防护网站
                      成功率: 较高
                      
  ④ tavily-fallback: Tavily Crawl/Extract API
                     适用: 所有失败的情况
                     成本: API调用（付费）

内容净化:
  - 移除噪声标签: script, style, nav, footer等
  - 移除样板文本: cookie、privacy、newsletter等
  - 定位主内容: <main> > <article> > role="main" > .content
  - 最大长度: 20000字符

返回结果:
  成功: (url, content, title) 或 json字典
  失败: ('', '', '') 或 None
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


# ---------------------------------------------------------------------------
# Domain Circuit Breaker - 自适应域名熔断器
# ---------------------------------------------------------------------------
class DomainCircuitBreaker:
    """自适应域名熔断器：运行时统计每个域名+路径前缀的成功/失败，连续失败超阈值后自动跳过。
    
    无需硬编码任何域名。无论目标是哪个网站，只要连续失败就会触发熔断。
    每次 research 任务创建一个新实例，任务结束后丢弃。
    
    熔断粒度: 域名 + 第一段路径 (例如 finance.yahoo.com/quote 和 finance.yahoo.com/news 独立计数)
    这样某个路径模式的失败不会牵连同域名下其他有用路径。
    
    参数:
        failure_threshold: 连续失败多少次后熔断该路径组 (默认3)
    """

    def __init__(self, failure_threshold: int = 3):
        self.failure_threshold = failure_threshold
        # key -> {failures, successes, consecutive_failures}
        self._stats: Dict[str, Dict[str, int]] = {}

    def should_skip(self, url: str) -> bool:
        """检查该URL的域名+路径组是否已被熔断。"""
        key = self._get_key(url)
        stats = self._stats.get(key)
        if not stats:
            return False
        return stats['consecutive_failures'] >= self.failure_threshold

    def record_success(self, url: str):
        """记录一次成功抓取。"""
        key = self._get_key(url)
        stats = self._ensure_stats(key)
        stats['successes'] += 1
        stats['consecutive_failures'] = 0

    def record_failure(self, url: str):
        """记录一次失败抓取。"""
        key = self._get_key(url)
        stats = self._ensure_stats(key)
        stats['failures'] += 1
        stats['consecutive_failures'] += 1

    def get_summary(self) -> Dict[str, Dict[str, int]]:
        """获取所有被熔断的路径组摘要（用于日志）。"""
        return {
            key: dict(s) for key, s in self._stats.items()
            if s['consecutive_failures'] >= self.failure_threshold
        }

    def _ensure_stats(self, key: str) -> Dict[str, int]:
        if key not in self._stats:
            self._stats[key] = {
                'failures': 0,
                'successes': 0,
                'consecutive_failures': 0,
            }
        return self._stats[key]

    # Locale-like short path segments (2-3 chars) that should be skipped for key granularity
    _LOCALE_SEGMENTS = frozenset([
        'nl', 'be', 'en', 'fr', 'de', 'es', 'it', 'pt', 'ja', 'ko', 'zh',
        'eu', 'us', 'uk', 'au', 'nz', 'sg', 'hk', 'ca', 'in',
    ])

    def _get_key(self, url: str) -> str:
        """获取熔断 key: 域名 + 有意义的路径前缀。
        
        跳过 locale 段 (nl, be, en, fr...) 取真正区分内容类型的路径段。
        
        例如:
          https://finance.yahoo.com/quote/BOL.BK → finance.yahoo.com/quote
          https://www.bol.com/nl/nl/p/product → www.bol.com/p
          https://www.bol.com/be/nl/l/bureaus/14247 → www.bol.com/l
          https://www.bol.com/nl/nl/klantenservice → www.bol.com/klantenservice
          https://x.com/JohnBol_7 → x.com/JohnBol_7
          https://over.bol.com/en/news/something → over.bol.com/news
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # 取路径段，跳过 locale 前缀
            path_parts = [p for p in parsed.path.split('/') if p]
            # Skip locale-like segments (short 2-3 char codes)
            meaningful = [p for p in path_parts if p.lower() not in self._LOCALE_SEGMENTS]
            if meaningful:
                return f"{domain}/{meaningful[0]}"
            elif path_parts:
                # All segments are locale-like, use last one
                return f"{domain}/{path_parts[-1]}"
            return domain
        except Exception:
            return url

# 浏览器User-Agent - 避免被识别为爬虫
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# 样板文本模式 - 需要移除的通用页面元素
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

# 需要完全移除的HTML标签
NOISE_TAGS = [
    "script", "style", "noscript", "iframe", "svg",
    "nav", "footer", "header",
]

MAX_TEXT_LENGTH = 20000  # 内容最大长度

# 定向抓取默认关键词（用于产品/品类相关页面）
DEFAULT_FOCUS_KEYWORDS = (
    "product", "products", "category", "categories", "solution", "solutions",
    "catalog", "collections", "portfolio", "shop", "store", "offerings",
)


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


def _discover_links(
    soup: BeautifulSoup,
    base_url: str,
    max_links: int = 50,
    focus_keywords: Optional[List[str]] = None,
    strict_focus: bool = False,
) -> List[str]:
    """Discover internal links from a page for crawling.

    When focus_keywords are provided, links matching those path keywords are ranked first.
    If strict_focus is True, only matched links are returned.
    """
    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc.lower()
    found = set()
    ranked_links = []
    normalized_focus = [k.strip().lower() for k in (focus_keywords or []) if k and k.strip()]

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

        is_focus_match = any(keyword in path_lower for keyword in normalized_focus) if normalized_focus else False
        if strict_focus and normalized_focus and not is_focus_match:
            continue

        if clean_url in found:
            continue

        found.add(clean_url)
        priority = 1 if is_focus_match else 0
        ranked_links.append((priority, clean_url))

    ranked_links.sort(key=lambda item: item[0], reverse=True)
    ordered_links = [url for _, url in ranked_links]

    return ordered_links[:max_links]


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
            timeout=10.0,
            verify=False,
        ) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp
            logger.debug(f"Fetch returned status {resp.status_code} for {url}")
            # Store status code for caller to check rejection
            resp._scrape_status = resp.status_code
            return resp if resp.status_code in (403, 401) else None
    except Exception as e:
        logger.debug(f"Fetch failed for {url}: {e}")
        return None


async def scrape_static(url: str) -> ScrapeResult:
    """Strategy 1: Static HTML fetch + content purification."""
    resp = await _fetch_page(url, enhanced=False)
    if not resp:
        return ScrapeResult(url=url, method="static", failure_reason="HTTP fetch failed")

    # Check for server rejection
    status = getattr(resp, '_scrape_status', resp.status_code)
    if status in (403, 401):
        return ScrapeResult(url=url, method="static",
                            failure_reason=f"HTTP {status} Forbidden")

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
    """Try strategies in order for a single URL, return first success.
    If static gets a clear rejection (403/401), skip enhanced to avoid wasting time."""
    # Try static first
    try:
        result = await scrape_static(url)
        if result.success:
            logger.info(f"[static] Success for {url} ({len(result.text)} chars)")
            return result
        # If we got a clear server rejection, don't bother with enhanced
        if result.failure_reason and any(code in result.failure_reason for code in ["403", "401", "Forbidden", "Unauthorized"]):
            return result
    except Exception as e:
        logger.debug(f"[static] Exception for {url}: {e}")

    # Try enhanced as fallback
    try:
        result = await scrape_enhanced(url)
        if result.success:
            logger.info(f"[enhanced-static] Success for {url} ({len(result.text)} chars)")
            return result
    except Exception as e:
        logger.debug(f"[enhanced-static] Exception for {url}: {e}")

    return ScrapeResult(
        url=url,
        method="all-failed",
        failure_reason="All scrape strategies failed",
    )


async def crawl_site(
    url: str,
    max_pages: int = 50,
    max_depth: int = 1,
    focus_keywords: Optional[List[str]] = None,
    strict_focus: bool = False,
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

        # Discover links from seed page using already-fetched content
        if max_depth > 0:
            resp = await _fetch_page(url)
            if resp:
                soup = BeautifulSoup(resp.text, "html.parser")
                discovered = _discover_links(
                    soup,
                    url,
                    max_links=max_pages,
                    focus_keywords=focus_keywords,
                    strict_focus=strict_focus,
                )
                to_visit.extend(discovered)

    # Crawl discovered pages concurrently
    remaining = [u for u in to_visit if u not in visited][:max_pages - 1]

    if remaining:
        semaphore = asyncio.Semaphore(10)

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

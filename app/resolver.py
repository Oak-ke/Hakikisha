"""Expand links, follow redirects, and capture the landing page as a phone would see it."""
import asyncio
import ipaddress
import re
import socket
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .config import settings

URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']+", re.IGNORECASE)
TRAILING = ".,;:!?)]}'\""

# Scam sites often "cloak": they show a harmless page to bots and the sales page
# to real users. Looking like an Android phone in Kenya gets the real page more often.
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; SM-A145F) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
)
HEADERS = {"User-Agent": MOBILE_UA, "Accept-Language": "en-KE,en;q=0.9,sw;q=0.8"}

META_REFRESH_RE = re.compile(
    r"<meta[^>]+http-equiv=[\"']?refresh[\"']?[^>]*content=[\"']?\s*\d+\s*;\s*url=([^\"'>\s]+)",
    re.IGNORECASE,
)
JS_REDIRECT_RE = re.compile(
    r"(?:window\.|document\.)?location(?:\.href)?\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE
)


def extract_urls(text: str, limit: int = 3) -> list[str]:
    out: list[str] = []
    for m in URL_RE.findall(text or ""):
        u = m.rstrip(TRAILING)
        if u.lower().startswith("www."):
            u = "https://" + u
        if u not in out:
            out.append(u)
    return out[:limit]


def host_error(url: str) -> str | None:
    """Return a reason if the URL must not be fetched (bad scheme, private IP, no DNS)."""
    try:
        p = urlparse(url)
    except ValueError:
        return "invalid link"
    if p.scheme not in ("http", "https") or not p.hostname:
        return "invalid link"
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except (socket.gaierror, UnicodeError):
        return "site does not exist or is offline"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return "blocked internal address"  # SSRF protection
    return None


def html_to_text(html: str, limit: int = 20_000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    parts = []
    if soup.title and soup.title.string:
        parts.append(soup.title.string)
    for meta in soup.find_all("meta", attrs={"name": ["description", "og:description"]}):
        if meta.get("content"):
            parts.append(meta["content"])
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    parts.append(soup.get_text(" ", strip=True))
    return re.sub(r"\s+", " ", " ".join(parts))[:limit]


@dataclass
class Resolved:
    original: str
    final_url: str
    chain: list[str] = field(default_factory=list)
    status: int | None = None
    html: str = ""
    text: str = ""
    error: str | None = None
    rendered: bool = False


def _next_hop(current: str, response: httpx.Response) -> str | None:
    if response.is_redirect and response.headers.get("location"):
        return urljoin(current, response.headers["location"])
    html = response.text[:500_000]
    m = META_REFRESH_RE.search(html)
    if not m and len(html) < 5000:  # tiny pages that only redirect via JS
        m = JS_REDIRECT_RE.search(html)
    if m:
        target = m.group(1).strip()
        if target and not target.startswith(("#", "javascript:")):
            return urljoin(current, target)
    return None


async def resolve(url: str, max_hops: int = 8, timeout: float = 10.0) -> Resolved:
    res = Resolved(original=url, final_url=url, chain=[url])
    current = url
    async with httpx.AsyncClient(follow_redirects=False, timeout=timeout, headers=HEADERS) as client:
        for _ in range(max_hops):
            err = await asyncio.to_thread(host_error, current)
            if err:
                res.error = err
                break
            try:
                r = await client.get(current)
            except httpx.HTTPError as e:
                res.error = f"could not load the site ({type(e).__name__})"
                break
            res.status = r.status_code
            nxt = _next_hop(current, r)
            if nxt is None:
                res.html = r.text[:500_000]
                break
            if nxt in res.chain:
                res.error = "redirect loop"
                break
            res.chain.append(nxt)
            current = nxt
    res.final_url = current
    if res.html:
        res.text = html_to_text(res.html)
    if settings.USE_BROWSER and not res.error:
        await _render(res)
    return res


async def _render(res: Resolved) -> None:
    """Optional: load the page in headless Chromium to run its JavaScript.

    Run this in an isolated container/network — a browser can still be pointed
    at internal addresses by page scripts.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            ctx = await browser.new_context(
                user_agent=MOBILE_UA, locale="en-KE", is_mobile=True,
                viewport={"width": 390, "height": 844},
            )
            page = await ctx.new_page()
            await page.goto(res.final_url, timeout=20_000, wait_until="networkidle")
            text = await page.inner_text("body")
            final = page.url
            await browser.close()
    except Exception:
        return
    if final and final != res.final_url:
        res.chain.append(final)
        res.final_url = final
    if len(text) > len(res.text):
        res.text = re.sub(r"\s+", " ", text)[:20_000]
    res.rendered = True

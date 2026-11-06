"""Domain-level red flags: age, lookalikes of Kenyan brands, risky TLDs, shorteners."""
import asyncio
import datetime as dt
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import tldextract

from ..config import settings
from ..models import Signal

# Use the bundled public-suffix snapshot so no network fetch is needed.
_extract = tldextract.TLDExtract(suffix_list_urls=())

_BRANDS_FILE = Path(__file__).resolve().parent.parent / "data" / "brands.json"
_data = json.loads(_BRANDS_FILE.read_text())
BRANDS: dict[str, set[str]] = {k: set(v) for k, v in _data["brands"].items()}
GOV_KEYWORDS: list[str] = _data["gov_keywords"]

SUSPICIOUS_TLDS = {
    "xyz", "top", "shop", "online", "site", "click", "buzz", "icu", "live",
    "store", "fun", "cyou", "sbs", "cfd", "rest", "monster", "life",
}
SHORTENERS = {
    "bit.ly", "tinyurl.com", "cutt.ly", "rb.gy", "t.ly", "is.gd", "shorturl.at",
    "ow.ly", "tiny.cc", "s.id", "rebrand.ly", "t.co", "lnkd.in", "shorturl.asia",
}


def registered_domain(url: str) -> str:
    ext = _extract(url)
    if not ext.suffix:
        return ext.domain
    return f"{ext.domain}.{ext.suffix}".lower()


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def lookalike_brand(url: str) -> str | None:
    """Return the brand a non-official domain seems to imitate, or None."""
    reg = registered_domain(url)
    for officials in BRANDS.values():
        if reg in officials:
            return None
    host = (urlparse(url).hostname or "").lower()
    compact = re.sub(r"[.\-_]", "", host)
    tokens = [t for t in re.split(r"[.\-_]", host) if t]
    for brand in BRANDS:
        if len(brand) >= 4 and brand in compact:
            return brand
        if len(brand) >= 5 and any(_levenshtein(t, brand) == 1 for t in tokens):
            return brand
        if len(brand) < 4 and brand in tokens:
            return brand
    return None


def gov_impersonation(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if host.endswith(".go.ke"):
        return False
    return any(k in host for k in GOV_KEYWORDS)


def _whois_age_days(domain: str) -> int | None:
    try:
        import whois  # python-whois
        w = whois.whois(domain)
    except Exception:
        return None
    created = w.creation_date
    if isinstance(created, list):
        created = min((c for c in created if isinstance(c, dt.datetime)), default=None)
    if not isinstance(created, dt.datetime):
        return None
    if created.tzinfo:
        created = created.astimezone(dt.timezone.utc).replace(tzinfo=None)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    return max((now - created).days, 0)


async def domain_age_days(domain: str) -> int | None:
    if not settings.ENABLE_WHOIS:
        return None
    try:
        return await asyncio.wait_for(asyncio.to_thread(_whois_age_days, domain), timeout=15)
    except (asyncio.TimeoutError, Exception):
        return None


def static_signals(final_url: str, chain: list[str]) -> list[Signal]:
    """Checks that need no network access."""
    out: list[Signal] = []
    p = urlparse(final_url)
    host = (p.hostname or "").lower()
    ext = _extract(final_url)

    brand = lookalike_brand(final_url)
    if brand:
        out.append(Signal("lookalike_domain", 45,
                          f"Website imitates '{brand}' but is not its official site",
                          f"Tovuti inaiga '{brand}' lakini si tovuti rasmi"))
    if gov_impersonation(final_url):
        out.append(Signal("gov_impersonation", 40,
                          "Looks like a government site but is not a .go.ke address",
                          "Inaonekana ya serikali lakini si anwani ya .go.ke"))
    try:
        ipaddress.ip_address(host)
        out.append(Signal("ip_host", 20, "Link uses a bare IP address instead of a name",
                          "Kiungo kinatumia anwani ya IP badala ya jina"))
    except ValueError:
        pass
    if ext.suffix.split(".")[-1] in SUSPICIOUS_TLDS:
        out.append(Signal("risky_tld", 10, f"Uses a cheap domain ending (.{ext.suffix}) common in scams",
                          f"Inatumia kiambishi (.{ext.suffix}) kinachotumika sana na matapeli"))
    if p.scheme == "http":
        out.append(Signal("no_https", 10, "Site is not secure (no https)",
                          "Tovuti si salama (haina https)"))
    hosts = {(urlparse(u).hostname or "").lower() for u in chain}
    if hosts & SHORTENERS:
        out.append(Signal("shortener", 5, "Real address was hidden behind a short link",
                          "Anwani halisi ilifichwa kwa kiungo kifupi"))
    if len(chain) > 4:
        out.append(Signal("many_redirects", 10, f"Link bounced through {len(chain) - 1} redirects",
                          f"Kiungo kilipitia njia {len(chain) - 1} za kuelekeza"))
    return out


def age_signal(days: int | None) -> list[Signal]:
    if days is None:
        return []
    if days < 30:
        return [Signal("new_domain", 35, f"Website was created only {days} days ago",
                       f"Tovuti iliundwa siku {days} tu zilizopita")]
    if days < 180:
        return [Signal("young_domain", 15, f"Website is new ({days} days old)",
                       f"Tovuti ni mpya (siku {days})")]
    return []

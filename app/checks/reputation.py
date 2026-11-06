"""Known-bad URL lists: Google Safe Browsing and VirusTotal. Skipped if no API key."""
import base64

import httpx

from ..config import settings
from ..models import Signal


async def safe_browsing(urls: list[str]) -> list[Signal]:
    # Note: the Safe Browsing Lookup API is for non-commercial use. For a commercial
    # product, switch to Google Cloud Web Risk (similar request shape).
    if not settings.SAFE_BROWSING_API_KEY or not urls:
        return []
    body = {
        "client": {"clientId": "hakiki", "clientVersion": "0.1"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE",
                            "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": u} for u in dict.fromkeys(urls)],
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                "https://safebrowsing.googleapis.com/v4/threatMatches:find",
                params={"key": settings.SAFE_BROWSING_API_KEY}, json=body,
            )
            r.raise_for_status()
            matches = r.json().get("matches", [])
    except (httpx.HTTPError, ValueError):
        return []
    if not matches:
        return []
    return [Signal("safe_browsing", 100, "Google lists this site as dangerous",
                   "Google imeorodhesha tovuti hii kuwa hatari", strong=True)]


async def virustotal(url: str) -> list[Signal]:
    if not settings.VIRUSTOTAL_API_KEY:
        return []
    url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://www.virustotal.com/api/v3/urls/{url_id}",
                            headers={"x-apikey": settings.VIRUSTOTAL_API_KEY})
        if r.status_code == 404:
            return []  # never scanned
        r.raise_for_status()
        stats = r.json()["data"]["attributes"]["last_analysis_stats"]
    except (httpx.HTTPError, KeyError, ValueError):
        return []
    malicious, suspicious = stats.get("malicious", 0), stats.get("suspicious", 0)
    if malicious >= 2:
        return [Signal("virustotal", 100, f"{malicious} security vendors flag this site",
                       f"Kampuni {malicious} za usalama zimeiripoti tovuti hii", strong=True)]
    if malicious or suspicious:
        return [Signal("virustotal_weak", 25, "A security vendor flagged this site",
                       "Kampuni ya usalama imeitilia shaka tovuti hii")]
    return []

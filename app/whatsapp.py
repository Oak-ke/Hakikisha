"""Send replies through the WhatsApp Cloud API. Without a token it just logs (dry run)."""
import hashlib
import hmac
import logging

import httpx

from .config import settings

log = logging.getLogger("hakiki.whatsapp")


def valid_signature(body: bytes, header: str | None) -> bool:
    """Check Meta's X-Hub-Signature-256 header. Skipped if no app secret is configured."""
    if not settings.WHATSAPP_APP_SECRET:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(settings.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


async def send_text(to: str, body: str) -> None:
    if not settings.WHATSAPP_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        log.info("[dry-run] to %s:\n%s", to, body)
        return
    url = (f"https://graph.facebook.com/{settings.GRAPH_API_VERSION}/"
           f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages")
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        # preview_url False: never unfurl a possibly malicious link in the reply
        "text": {"body": body[:4096], "preview_url": False},
    }
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, json=payload,
                         headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"})
        if r.status_code >= 400:
            log.error("WhatsApp send failed %s: %s", r.status_code, r.text[:300])

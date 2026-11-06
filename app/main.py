"""FastAPI app: WhatsApp webhook, a JSON /check endpoint, and an admin endpoint."""
import json
import logging
from collections import OrderedDict
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .checks.domain import registered_domain
from .checks.landing import extract_entities
from .config import settings
from .db import get_db
from .pipeline import check_message
from .resolver import extract_urls
from .scoring import detect_lang, format_reply
from .whatsapp import send_text, valid_signature

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hakiki")

HELP = (
    "👋 Hakiki checks links and ads before you pay.\n\n"
    "• Send or forward a link from Facebook, TikTok or Instagram\n"
    "• Or paste the ad text\n"
    "• Reply REPORT <link or number> if something scammed you",
    "👋 Hakiki hukagua viungo na matangazo kabla hujalipa.\n\n"
    "• Tuma au sambaza kiungo kutoka Facebook, TikTok au Instagram\n"
    "• Au bandika maandishi ya tangazo\n"
    "• Jibu RIPOTI <kiungo au namba> kama umetapeliwa",
)
GREETINGS = {"hi", "hello", "help", "start", "habari", "msaada", "mambo", "sasa"}

_seen: OrderedDict[str, None] = OrderedDict()  # Meta retries webhooks; skip duplicates


def _first_time(message_id: str) -> bool:
    if message_id in _seen:
        return False
    _seen[message_id] = None
    if len(_seen) > 5000:
        _seen.popitem(last=False)
    return True


@asynccontextmanager
async def lifespan(_app):
    get_db()
    yield


app = FastAPI(title="Hakiki — link & ad checker", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/webhook")
def verify(request: Request):
    q = request.query_params
    if q.get("hub.mode") == "subscribe" and q.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(q.get("hub.challenge", ""))
    raise HTTPException(status_code=403)


@app.post("/webhook")
async def receive(request: Request, background: BackgroundTasks):
    body = await request.body()
    if not valid_signature(body, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(status_code=403)
    data = json.loads(body or b"{}")
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []):
                if not _first_time(m.get("id", "")):
                    continue
                kind = m.get("type", "")
                part = m.get(kind) if isinstance(m.get(kind), dict) else {}
                text = part.get("body") or part.get("caption") or ""  # text body or media caption
                background.add_task(handle_message, m["from"], text, kind)
    return {"ok": True}  # reply fast; work happens in the background


def record_report(text: str) -> int:
    db = get_db()
    count = 0
    for u in extract_urls(text):
        db.report("domain", registered_domain(u), note=text[:200])
        db.report("url", u)
        count += 1
    ent = extract_entities(text)
    for p in ent["phone"]:
        db.report("phone", p, note=text[:200])
        count += 1
    for t in ent["till"]:
        db.report("till", t, note=text[:200])
        count += 1
    return count


async def handle_message(sender: str, text: str, kind: str) -> None:
    lang = detect_lang(text)
    i = 1 if lang == "sw" else 0
    try:
        if not text.strip():
            if kind in ("image", "video"):
                await send_text(sender, (
                    "Screenshot checks are coming soon. For now, send the link or paste the ad text.",
                    "Ukaguzi wa picha unakuja hivi karibuni. Kwa sasa, tuma kiungo au bandika maandishi ya tangazo.",
                )[i])
            return
        words = text.strip().split(maxsplit=1)
        if words[0].upper() in ("REPORT", "RIPOTI"):
            n = record_report(words[1] if len(words) > 1 else "")
            await send_text(sender, (
                f"Thank you. {n} item(s) recorded for review — this helps protect others.",
                f"Asante. Vitu {n} vimerekodiwa kwa ukaguzi — hii inawalinda wengine.",
            )[i] if n else ("Send REPORT followed by the link or phone number.",
                            "Tuma RIPOTI ikifuatiwa na kiungo au namba ya simu.")[i])
            return
        if text.strip().lower() in GREETINGS:
            await send_text(sender, HELP[i])
            return
        await send_text(sender, ("🔎 Checking… this takes a few seconds.",
                                 "🔎 Inakagua… subiri sekunde chache.")[i])
        results = await check_message(text)
        await send_text(sender, format_reply(results, lang))
    except Exception:
        log.exception("failed to handle message")
        await send_text(sender, ("Sorry, something went wrong. Please try again.",
                                 "Samahani, kuna hitilafu. Tafadhali jaribu tena.")[i])


class CheckIn(BaseModel):
    text: str
    lang: str | None = None


@app.post("/check")
async def check(payload: CheckIn):
    """Same checks as WhatsApp, for a web front end or testing."""
    results = await check_message(payload.text)
    lang = payload.lang or detect_lang(payload.text)
    return {"results": [r.to_dict() for r in results], "reply": format_reply(results, lang)}


class IndicatorIn(BaseModel):
    kind: str      # domain | url | phone | till
    value: str
    status: str    # confirmed | cleared | reported
    note: str = ""


@app.post("/admin/indicators")
def set_indicator(payload: IndicatorIn, x_admin_token: str = Header(default="")):
    """Reviewer confirms (or clears) a reported scam. Confirmed items trigger HIGH instantly."""
    if not settings.ADMIN_TOKEN or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=403)
    if payload.kind not in ("domain", "url", "phone", "till") or \
            payload.status not in ("confirmed", "cleared", "reported"):
        raise HTTPException(status_code=422, detail="bad kind or status")
    get_db().set_status(payload.kind, payload.value, payload.status, payload.note)
    return {"ok": True}

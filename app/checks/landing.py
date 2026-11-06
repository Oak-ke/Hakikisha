"""Red-flag patterns in ad or landing-page text (English and Swahili), plus entity extraction."""
import re
from dataclasses import dataclass

from ..models import Signal


@dataclass
class Rule:
    code: str
    weight: int
    patterns: list[str]
    en: str
    sw: str

    def __post_init__(self):
        self._re = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def matches(self, text: str) -> bool:
        return any(r.search(text) for r in self._re)


RULES = [
    Rule("cure_claim", 25, [
        r"\b100\s*%\s*(cure|natural|guaranteed|effective|results)",
        r"\b(permanent(ly)?|complete(ly)?|total(ly)?)\s+(cure|heal)",
        r"\bcures?\s+(in|within)\s+\d+\s*(days?|hours?|weeks?)",
        r"\bmiracle\b", r"\bguaranteed\s+(cure|results)",
        r"\btiba\s+ya\s+kudumu\b", r"\bpona\s+kabisa\b", r"\bdawa\s+ya\s+asili\b",
    ], "Promises a miracle or guaranteed cure", "Inaahidi tiba ya muujiza au ya uhakika"),
    Rule("health_target", 10, [
        r"\bprostat", r"\btezi\s+dume", r"\berectile", r"\bnguvu\s+za\s+kiume",
        r"\bdiabet", r"\bkisukari", r"\bjoint\s+pain", r"\bmaumivu\s+ya\s+viungo",
        r"\bhypertension", r"\bpresha\b", r"\bhigh\s+blood\s+pressure",
    ], "Targets a chronic health condition", "Inalenga ugonjwa sugu"),
    Rule("doctor_secret", 20, [
        r"doctors?\s+(don'?t|do\s+not|hate|hide|won'?t)",
        r"pharma(ceutical)?\s+compan(y|ies)\s+(hide|don'?t\s+want|hate)",
        r"\bsecret\s+(remedy|cure|formula|method)",
    ], "Claims doctors are hiding this from you", "Inadai madaktari wanakuficha hili"),
    Rule("urgency", 15, [
        r"\bonly\s+\d+\s+(left|remaining|pieces|packs|bottles)",
        r"\boffer\s+ends\b", r"\blimited\s+(stock|offer|time)\b", r"\bhurry\b",
        r"\bimebaki\s+\d+", r"\bleo\s+tu\b", r"\bpromo(tion)?\s+ends\b",
    ], "Pressures you to buy quickly", "Inakulazimisha kununua haraka"),
    Rule("pay_first", 25, [
        r"\btill\s*(no\.?|number|#)?\s*:?\s*\d{5,7}",
        r"\bpay\s*bill\s*(no\.?|number|#)?\s*:?\s*\d{5,7}",
        r"\blipa\s+na\s+m-?pesa\b", r"\bpay\s+(before|first|in\s+advance)\b",
        r"\bsend\s+(money|payment|the\s+money)\s+to\b", r"\btuma\s+pesa\b",
    ], "Asks for M-Pesa payment up front", "Inaomba malipo ya M-Pesa kwanza"),
    Rule("whatsapp_order", 5, [
        r"wa\.me/", r"api\.whatsapp\.com", r"order\s+(via|on|through)\s+whatsapp",
    ], "Orders only through WhatsApp", "Maagizo kupitia WhatsApp tu"),
    Rule("fake_news_frame", 15, [
        r"\bbreaking\s+news\b", r"\bexclusive\s+interview\b",
        r"\b(citizen\s+tv|ntv\s+kenya|ktn\s+news|nation\s+media)\b",
        r"\bas\s+seen\s+on\s+(tv|citizen|ntv|ktn)\b",
    ], "Dressed up as a news story", "Imepambwa ionekane kama habari"),
    Rule("endorsement", 15, [
        r"\b(dr|doctor|prof)\.?\s+\w+\s+(reveals|recommends|discovered|explains|confirms)",
        r"\bendorsed\s+by\b",
        r"\bapproved\s+by\s+(the\s+)?(ministry|who|kebs|ppb|kemri)\b",
    ], "Uses a doctor's or official's name to sell", "Inatumia jina la daktari au taasisi kuuza"),
    Rule("big_numbers", 10, [
        r"\b\d{1,3}[,.]\d{3}\s+(people|customers|kenyans|men|women)\s+(have\s+)?(bought|ordered|been\s+cured|cured)",
        r"\bsold\s+out\s+\d+\s+times\b",
    ], "Quotes huge, unverifiable sales or cure numbers", "Inataja takwimu kubwa zisizothibitishwa"),
]

PHONE_RE = re.compile(r"(?<!\d)(?:\+?254|0)\s?(?:7|1)\d{2}\s?\d{3}\s?\d{3}(?!\d)")
TILL_RE = re.compile(r"\b(?:till|pay\s*bill)\s*(?:no\.?|number|#)?\s*:?\s*(\d{5,7})\b", re.IGNORECASE)


def normalise_phone(raw: str) -> str:
    d = re.sub(r"\D", "", raw)
    return "254" + d[1:] if d.startswith("0") else d


def extract_entities(text: str) -> dict[str, list[str]]:
    phones = list(dict.fromkeys(normalise_phone(m) for m in PHONE_RE.findall(text or "")))
    tills = list(dict.fromkeys(TILL_RE.findall(text or "")))
    return {"phone": phones, "till": tills}


def analyse_text(text: str) -> list[Signal]:
    if not text:
        return []
    hits = [r for r in RULES if r.matches(text)]
    out = [Signal(r.code, r.weight, r.en, r.sw) for r in hits]
    codes = {r.code for r in hits}
    if {"cure_claim", "health_target"} <= codes:
        out.append(Signal("health_scam_combo", 15,
                          "Matches the pattern of fake medicine ads",
                          "Inafanana na matangazo ya dawa feki"))
    return out

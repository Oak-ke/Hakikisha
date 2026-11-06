"""Turn signals into a risk level and a short, plain-language reply."""
import re
from urllib.parse import urlparse

from .models import CheckResult, Level

HIGH_AT = 60
CAUTION_AT = 30

SW_WORDS = {
    "habari", "tafadhali", "hii", "ni", "je", "dawa", "nisaidie", "kweli", "sawa",
    "kiungo", "angalia", "hiki", "hapa", "naomba", "kagua", "hili", "huu", "mambo",
    "ya", "kwa", "wa", "za", "tu", "leo", "pesa", "tuma", "kabisa", "sana", "nini",
    "gani", "hapana", "ndio", "msaada", "sasa", "asante", "yangu", "wangu", "hiyo",
}


def score(r: CheckResult) -> CheckResult:
    total = sum(s.weight for s in r.signals)
    r.score = min(total, 100)
    if any(s.strong for s in r.signals) or total >= HIGH_AT:
        r.level = Level.HIGH
    elif total >= CAUTION_AT:
        r.level = Level.CAUTION
    elif not r.fetched:
        r.level = Level.UNVERIFIED
    else:
        r.level = Level.LOW
    return r


def detect_lang(text: str) -> str:
    tokens = re.findall(r"[a-z]+", (text or "").lower())
    hits = len(set(tokens) & SW_WORDS)
    # two Swahili words, or one in a very short message ("habari", "msaada")
    return "sw" if hits >= 2 or (hits == 1 and len(tokens) <= 3) else "en"


HEAD = {
    Level.HIGH: ("🔴 High risk — likely a scam", "🔴 Hatari kubwa — huenda ni utapeli"),
    Level.CAUTION: ("🟠 Be careful", "🟠 Kuwa mwangalifu"),
    Level.LOW: ("🟢 No red flags found", "🟢 Hakuna dalili za hatari zilizopatikana"),
    Level.UNVERIFIED: ("⚪ Couldn't check this", "⚪ Haikuweza kukaguliwa"),
}
ACTION = {
    Level.HIGH: ("Don't pay and don't share your details. Buy medicine only from a licensed pharmacy.",
                 "Usilipe wala usitoe taarifa zako. Nunua dawa kwa famasia iliyosajiliwa tu."),
    Level.CAUTION: ("Don't pay until the seller is checked with someone you trust or on the PPB register.",
                    "Usilipe hadi muuzaji athibitishwe na mtu unayemwamini au kwenye orodha ya PPB."),
    Level.LOW: ("This is not proof it's genuine. Never pay a stranger in advance.",
                "Hii si uthibitisho kuwa ni halali. Usimlipe mgeni pesa mapema."),
    Level.UNVERIFIED: ("The site didn't load or couldn't be checked. Treat it with care.",
                       "Tovuti haikufunguka au haikuweza kukaguliwa. Kuwa mwangalifu."),
}
FOOTER = (
    "Scammed or think this is wrong? Reply: REPORT <link or number>",
    "Umetapeliwa au tumekosea? Jibu: RIPOTI <kiungo au namba>",
)


def _label(r: CheckResult) -> str:
    url = r.final_url or ""
    host = urlparse(url).hostname if url.startswith("http") else None
    if host:
        return host
    return (r.input[:60] + "…") if len(r.input) > 60 else r.input


def format_reply(results: list[CheckResult], lang: str = "en") -> str:
    i = 1 if lang == "sw" else 0
    blocks = []
    for r in results:
        lines = [HEAD[r.level][i], _label(r)]
        top = sorted(r.signals, key=lambda s: s.weight, reverse=True)[:3]
        lines += [f"• {s.sw if i else s.en}" for s in top]
        if r.level is Level.UNVERIFIED and r.error:
            lines.append(f"• {r.error}")
        lines += ["", ACTION[r.level][i]]
        blocks.append("\n".join(lines))
    blocks.append(FOOTER[i])
    return "\n\n".join(blocks)

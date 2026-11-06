"""Run every check on a link (or on pasted ad text) and score the result."""
import asyncio

from .checks import domain, landing, reputation
from .checks.llm import llm_signals
from .db import get_db, signals_from_rows
from .models import CheckResult
from .resolver import extract_urls, resolve
from .scoring import score


def _indicator_pairs(chain: list[str], entities: dict[str, list[str]]) -> list[tuple[str, str]]:
    pairs = [("domain", domain.registered_domain(u)) for u in chain]
    pairs += [("url", u) for u in chain]
    pairs += [("phone", p) for p in entities.get("phone", [])]
    pairs += [("till", t) for t in entities.get("till", [])]
    return pairs


async def check_url(url: str) -> CheckResult:
    r = CheckResult(input=url)
    res = await resolve(url)
    r.chain, r.final_url, r.error = res.chain, res.final_url, res.error
    r.fetched = bool(res.text)

    age_task = domain.domain_age_days(domain.registered_domain(res.final_url))
    sb_task = reputation.safe_browsing(res.chain)
    vt_task = reputation.virustotal(res.final_url)
    llm_task = llm_signals(res.text)
    age, sb, vt, llm = await asyncio.gather(age_task, sb_task, vt_task, llm_task)

    r.entities = landing.extract_entities(res.text)
    r.signals += domain.static_signals(res.final_url, res.chain)
    r.signals += domain.age_signal(age)
    r.signals += sb + vt
    r.signals += landing.analyse_text(res.text)
    r.signals += llm

    db = get_db()
    r.signals += signals_from_rows(db.lookup(_indicator_pairs(res.chain, r.entities)))
    score(r)
    db.log_check(r)
    return r


async def check_plain_text(text: str) -> CheckResult:
    """For pasted ad text with no link."""
    r = CheckResult(input=text, fetched=True)
    r.entities = landing.extract_entities(text)
    r.signals += landing.analyse_text(text)
    r.signals += await llm_signals(text)
    db = get_db()
    r.signals += signals_from_rows(db.lookup(_indicator_pairs([], r.entities)))
    score(r)
    db.log_check(r)
    return r


async def check_message(text: str) -> list[CheckResult]:
    urls = extract_urls(text)
    if not urls:
        return [await check_plain_text(text)]
    return list(await asyncio.gather(*(check_url(u) for u in urls)))

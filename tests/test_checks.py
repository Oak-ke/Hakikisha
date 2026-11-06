"""Offline tests: no network calls are made."""
import asyncio

import pytest

from app import db as dbmod
from app import pipeline
from app.checks import domain, landing
from app.models import CheckResult, Level, Signal
from app.resolver import Resolved, extract_urls, host_error
from app.scoring import detect_lang, format_reply, score

PROSTATE_AD = (
    "BREAKING NEWS: Dr. Kamau reveals the secret remedy doctors don't want you to know. "
    "100% natural cure for prostate problems in 7 days! Only 5 bottles left. "
    "Lipa na M-Pesa till number 5123456 then WhatsApp 0712 345 678."
)


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    dbmod.set_db(dbmod.DB(str(tmp_path / "test.db")))
    monkeypatch.setattr("app.config.settings.ENABLE_WHOIS", False)
    yield


def test_extract_urls():
    text = "Check this www.cure-now.xyz/offer, and https://bit.ly/abc)."
    assert extract_urls(text) == ["https://www.cure-now.xyz/offer", "https://bit.ly/abc"]


def test_blocks_internal_addresses():
    assert host_error("http://127.0.0.1/admin") == "blocked internal address"
    assert host_error("ftp://example.com") == "invalid link"


def test_landing_flags_prostate_scam():
    codes = {s.code for s in landing.analyse_text(PROSTATE_AD)}
    assert {"cure_claim", "health_target", "health_scam_combo", "urgency",
            "pay_first", "fake_news_frame", "doctor_secret"} <= codes


def test_landing_swahili():
    codes = {s.code for s in landing.analyse_text("Dawa ya asili ya tezi dume, pona kabisa! Tuma pesa leo tu.")}
    assert {"cure_claim", "health_target", "pay_first", "urgency"} <= codes


def test_entities():
    ent = landing.extract_entities(PROSTATE_AD)
    assert ent["phone"] == ["254712345678"]
    assert ent["till"] == ["5123456"]


def test_lookalike_domains():
    assert domain.lookalike_brand("https://safaricom-bonus.xyz/claim") == "safaricom"
    assert domain.lookalike_brand("https://safarlcom.co.ke") == "safaricom"
    assert domain.lookalike_brand("https://www.safaricom.co.ke/personal") is None
    assert domain.lookalike_brand("https://example.com") is None
    assert domain.gov_impersonation("https://ministry-health-ke.com")
    assert not domain.gov_impersonation("https://health.go.ke")


def test_scoring_levels():
    r = score(CheckResult(input="x", fetched=True,
                          signals=[Signal("a", 25, "", ""), Signal("b", 10, "", "")]))
    assert r.level is Level.CAUTION
    r = score(CheckResult(input="x", fetched=True, signals=[]))
    assert r.level is Level.LOW
    r = score(CheckResult(input="x", fetched=False, signals=[]))
    assert r.level is Level.UNVERIFIED
    r = score(CheckResult(input="x", signals=[Signal("k", 100, "", "", strong=True)]))
    assert r.level is Level.HIGH


def test_detect_lang():
    assert detect_lang("Habari, tafadhali angalia hii") == "sw"
    assert detect_lang("Is this legit?") == "en"


def test_plain_text_check_is_high_risk():
    [r] = asyncio.run(pipeline.check_message(PROSTATE_AD))
    assert r.level is Level.HIGH
    reply = format_reply([r], "en")
    assert reply.startswith("🔴") and "Don't pay" in reply


def test_url_pipeline_with_fake_fetch(monkeypatch):
    async def fake_resolve(url):
        final = "https://prostate-cure-ke.shop/order"
        return Resolved(original=url, final_url=final, chain=[url, final], text=PROSTATE_AD)

    monkeypatch.setattr(pipeline, "resolve", fake_resolve)
    [r] = asyncio.run(pipeline.check_message("is this real? https://bit.ly/abc123"))
    codes = {s.code for s in r.signals}
    assert {"shortener", "risky_tld", "pay_first"} <= codes
    assert r.level is Level.HIGH


def test_confirmed_report_is_strong(monkeypatch):
    async def fake_resolve(url):
        return Resolved(original=url, final_url=url, chain=[url], text="Welcome to our shop")

    monkeypatch.setattr(pipeline, "resolve", fake_resolve)
    dbmod.get_db().set_status("domain", "quiet-scam.com", "confirmed")
    [r] = asyncio.run(pipeline.check_message("https://quiet-scam.com/page"))
    assert r.level is Level.HIGH
    assert any(s.code == "known_scam_domain" for s in r.signals)


def test_report_command_records(monkeypatch):
    from app.main import record_report
    assert record_report("https://fake-cure.xyz 0722000111") == 2
    rows = dbmod.get_db().lookup([("domain", "fake-cure.xyz"), ("phone", "254722000111")])
    assert len(rows) == 2

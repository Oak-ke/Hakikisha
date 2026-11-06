from fastapi.testclient import TestClient

from app import db as dbmod
from app import main


def _payload(text, mid="wamid.1"):
    return {"entry": [{"changes": [{"value": {"messages": [
        {"from": "254700000001", "id": mid, "type": "text", "text": {"body": text}}
    ]}}]}]}


def test_verify_and_receive(tmp_path, monkeypatch):
    dbmod.set_db(dbmod.DB(str(tmp_path / "t.db")))
    sent = []

    async def fake_send(to, body):
        sent.append((to, body))

    monkeypatch.setattr(main, "send_text", fake_send)
    monkeypatch.setattr("app.config.settings.WHATSAPP_VERIFY_TOKEN", "tok")
    client = TestClient(main.app)

    r = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "tok",
                                       "hub.challenge": "42"})
    assert r.text == "42"
    assert client.get("/webhook", params={"hub.mode": "subscribe",
                                          "hub.verify_token": "bad"}).status_code == 403

    ad = "Miracle cure for prostate in 3 days! Lipa na M-Pesa till 512345 now, only 2 left"
    assert client.post("/webhook", json=_payload(ad)).status_code == 200
    client.post("/webhook", json=_payload(ad))  # duplicate id is ignored
    assert len(sent) == 2  # "checking…" + verdict
    assert sent[1][1].startswith("🔴")

    client.post("/webhook", json=_payload("habari", mid="wamid.2"))
    assert "Hakiki hukagua" in sent[-1][1]


def test_check_endpoint(tmp_path):
    dbmod.set_db(dbmod.DB(str(tmp_path / "t.db")))
    client = TestClient(main.app)
    r = client.post("/check", json={"text": "Dawa ya asili, pona kabisa tezi dume. Tuma pesa leo tu"})
    body = r.json()
    assert body["results"][0]["level"] in ("high", "caution")
    assert "Usilipe" in body["reply"]

# Hakiki — link & ad checker

A WhatsApp bot that checks links and ads from Facebook, TikTok and Instagram **before** someone pays.
Forward a link, or paste the ad text, and Hakiki replies in English or Swahili with a risk level,
the main reasons, and what to do.

```
🔴 High risk — likely a scam
prostate-cure-ke.shop
• Website was created only 9 days ago
• Promises a miracle or guaranteed cure
• Asks for M-Pesa payment up front

Don't pay and don't share your details. Buy medicine only from a licensed pharmacy.
```

It judges whether the **offer is safe**, not whether a video is real. It never says "safe" —
the lowest level is "no red flags found".

## How it works

```
WhatsApp message ─► resolver ─► link checks ─┐
  (link or text)    unshorten,   advertiser* ├─► scoring ─► reply (EN/SW)
                    render page  content     ┘
                                    ▲
                     reported / confirmed scams (SQLite)
```

| Module | What it does |
|---|---|
| `app/resolver.py` | Follows redirects (HTTP, meta-refresh, JS stubs) as an Android phone in Kenya; blocks internal IPs; optional Playwright rendering |
| `app/checks/domain.py` | Domain age (WHOIS), lookalikes of Kenyan brands (`data/brands.json`), fake government sites, risky TLDs, shorteners |
| `app/checks/reputation.py` | Google Safe Browsing, VirusTotal |
| `app/checks/landing.py` | English + Swahili red-flag rules (miracle cures, urgency, M-Pesa upfront, fake news framing…), extracts phone and till numbers |
| `app/checks/llm.py` | Optional Claude review of the page text, returning JSON flags |
| `app/db.py` | Reported/confirmed scam domains, links, phones and tills; log of checks |
| `app/scoring.py` | Weighted score → `high / caution / low / unverified`; reply text |
| `app/main.py` | FastAPI: `/webhook` (WhatsApp), `/check` (JSON), `/admin/indicators` |

\* Advertiser/Page-transparency checks are the next phase (see roadmap). Meta's Ad Library API
does not return commercial ads shown outside the EU/UK, so this MVP works from what the user sends.

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # all keys optional for local testing
pytest -q                     # offline tests
python -m app.cli "https://bit.ly/some-link"
python -m app.cli "Dawa ya asili ya tezi dume, pona kabisa! Tuma pesa leo tu" --sw
uvicorn app.main:app --reload
curl -X POST localhost:8000/check -H 'content-type: application/json' -d '{"text":"https://example.com"}'
```

Without `WHATSAPP_TOKEN` the bot runs in dry-run mode and logs replies instead of sending them.

## Connect WhatsApp

1. Create an app at developers.facebook.com → add the **WhatsApp** product.
2. Copy the temporary token and phone number ID into `.env`; set `WHATSAPP_APP_SECRET` (App settings → Basic).
3. Expose your server (e.g. `ngrok http 8000`) and set the webhook URL to `https://<host>/webhook`
   with your `WHATSAPP_VERIFY_TOKEN`. Subscribe to the `messages` field.
4. Add your parents' numbers as test recipients and message the test number.
5. Check `GRAPH_API_VERSION` against Meta's current version before going live.

## Bot commands

- Any link or ad text → check
- `REPORT <link or number>` / `RIPOTI …` → records it for review
- `hi`, `help`, `habari`, `msaada` → instructions

## Reviewing reports

User reports count weakly (10 points, 30 after three reports). A reviewer promotes them:

```bash
curl -X POST localhost:8000/admin/indicators -H "X-Admin-Token: $ADMIN_TOKEN" \
  -H 'content-type: application/json' \
  -d '{"kind":"domain","value":"prostate-cure-ke.shop","status":"confirmed","note":"fake prostate drug"}'
```

Confirmed items make any later check **High risk** instantly — re-uploaded scams are caught at once.

## Tuning

- Weights live next to each signal; thresholds are `HIGH_AT=60`, `CAUTION_AT=30` in `scoring.py`.
- Add rules to `RULES` in `landing.py` as you see new scam scripts.
- **Verify every domain in `data/brands.json`** before production, and add more brands.

## Before launch

- **Data protection:** Kenya's Data Protection Act applies (you process people's messages).
  Register with the ODPC, publish a privacy notice, keep only what you need.
- **Safe Browsing licence:** the Lookup API is non-commercial; use Google Cloud Web Risk for a paid product.
- **Wording:** keep verdicts factual ("matches scam patterns", "not on the register") to limit defamation risk.
- **Isolation:** run the fetcher/browser in a sandboxed network; it visits hostile sites.

## Roadmap

1. **Screenshots:** OCR ad images (Tesseract or a vision model) → same pipeline.
2. **Advertiser checks:** read a Page's public transparency info (creation date, name changes,
   manager countries); check Meta's terms before scraping, or seek researcher access.
3. **Registries:** PPB pharmacy list and KMPDC doctor register lookups.
4. **Scam-script matching:** embeddings (pgvector) to catch reused ad copy.
5. **Move to Postgres + a job queue** (Redis/Celery) when traffic grows.
6. **Partnerships:** Africa Check, PPB, Safaricom fraud desk.

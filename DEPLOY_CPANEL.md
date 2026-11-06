# Deploy Hakikisha on a cPanel server

One cPanel Python app runs everything: the web page at `/`, the full checks at `/check`,
and the WhatsApp webhook at `/webhook`.

The examples use the subdomain `check.nobaloak.co.ke`. Replace it with yours, and replace
`USER` with your cPanel username.

## 0. Requirements

- cPanel with **Setup Python App** (under *Software*). Most CloudLinux hosts have it.
- **Python 3.10 or newer** in that tool's version list. If it only offers 3.9 or older, ask your host.
- SSH/Terminal access helps but isn't required.

## 1. Create a subdomain

*Domains* → *Create A New Domain* → `check.nobaloak.co.ke`.
A subdomain is cleaner than a sub-folder, because the app expects to run at the root of its address.

## 2. Get the code onto the server

Pick one:

- **Git Version Control** (cPanel → *Files*): *Create* → Clone URL `https://github.com/Oak-ke/Hakikisha.git`,
  Repository path `/home/USER/hakikisha`.
- **Terminal**: `git clone https://github.com/Oak-ke/Hakikisha.git ~/hakikisha`
- **File Manager**: upload the repo zip to `/home/USER/hakikisha` and extract.

Keep it **outside `public_html`** so `.env` and the database are never downloadable.

## 3. Create the Python app

*Setup Python App* → *Create Application*:

| Field | Value |
|---|---|
| Python version | 3.11 or 3.12 (anything ≥ 3.10) |
| Application root | `hakikisha` |
| Application URL | `check.nobaloak.co.ke` (leave the path empty) |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |
| Passenger log file | `/home/USER/logs/hakikisha.log` |

Click **Create**.

## 4. Install the dependencies

On the app's page, under *Configuration files*, add `requirements.txt` and click **Run Pip Install**.

Or in Terminal, run the `source …/activate` command shown at the top of the app page, then:

```bash
cd ~/hakikisha
pip install -r requirements.txt
```

## 5. Set the configuration

Either add *Environment variables* on the app page, or create `/home/USER/hakikisha/.env`
by copying `.env.example`. At minimum:

```
DB_PATH=/home/USER/hakikisha-data/hakikisha.db
ADMIN_TOKEN=<long random string>
ENABLE_WHOIS=true
USE_BROWSER=false
ALLOWED_ORIGINS=https://oak-ke.github.io
```

Create the data folder: `mkdir -p ~/hakikisha-data`

Add the WhatsApp, VirusTotal, Safe Browsing and Anthropic keys whenever you're ready.
Each check is skipped until its key is set.

Click **Restart** on the app page after any change.

## 6. Turn on HTTPS

*SSL/TLS Status* → tick the subdomain → **Run AutoSSL**. WhatsApp only accepts `https://` webhooks.

## 7. Test it

- `https://check.nobaloak.co.ke` should show the checker page. Results should say *"Full check: the website was opened and tested."*
- `https://check.nobaloak.co.ke/health` should return `{"ok":true}`.

## 8. Connect WhatsApp

In Meta → WhatsApp → *Configuration* → Webhook:

- Callback URL `https://check.nobaloak.co.ke/webhook`
- Verify token: your `WHATSAPP_VERIFY_TOKEN`

Then **subscribe to `messages`**. See the README for the rest of the Meta setup.

## Updating

```bash
cd ~/hakikisha && git pull
touch tmp/restart.txt      # or click Restart in Setup Python App
```

If dependencies changed, also run the pip install from step 4.

## Troubleshooting

| Problem | Fix |
|---|---|
| 503 / "Incomplete response" | Read `/home/USER/logs/hakikisha.log` — usually a missing package |
| `ModuleNotFoundError` | Packages went into the wrong environment. Run the `source …/activate` command from the app page first, then pip install |
| Domain age never shows | Shared hosts often block outbound WHOIS (port 43). Set `ENABLE_WHOIS=false` |
| First request after a while is slow | Passenger stops idle apps and starts them on the next visit. This is normal on shared hosting |
| Page loads but always says "Quick check in your browser" | `/config.js` isn't reaching the app. Check that the Application URL is the subdomain root |

Leave `USE_BROWSER=false`: headless Chrome (Playwright) doesn't run on shared cPanel hosting.
Use a VPS if you need it.

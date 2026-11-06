"""Settings loaded from environment variables (see .env.example)."""
import os

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    # WhatsApp Cloud API (Meta)
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "change-me")
    WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
    GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v23.0")

    # Reputation services (optional — checks are skipped when a key is missing)
    SAFE_BROWSING_API_KEY = os.getenv("SAFE_BROWSING_API_KEY", "")
    VIRUSTOTAL_API_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")

    # LLM review (optional)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")

    # Behaviour
    USE_BROWSER = _bool("USE_BROWSER", False)  # render pages with Playwright
    ENABLE_WHOIS = _bool("ENABLE_WHOIS", True)
    DB_PATH = os.getenv("DB_PATH", "hakiki.db")
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
    # Web pages on other domains allowed to call /check (comma-separated)
    ALLOWED_ORIGINS = [o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS", "https://oak-ke.github.io").split(",") if o.strip()]


settings = Settings()

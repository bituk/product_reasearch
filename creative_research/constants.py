"""
Centralized environment variables and constants.
Load .env from project root on import.
"""
import os
from pathlib import Path

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_ENV_PATH)
    except ImportError:
        pass


def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    return os.environ.get(key, "").lower() in ("1", "true", "yes")


def _env_float(key: str, default: float = 0) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


# --- API Keys ---
OPENAI_API_KEY = _env("OPENAI_API_KEY")
APIFY_API_TOKEN = _env("APIFY_API_TOKEN")
YOUTUBE_API_KEY = _env("YOUTUBE_API_KEY")
GOOGLE_API_KEY = _env("GOOGLE_API_KEY")
YOUTUBE_OR_GOOGLE_API_KEY = YOUTUBE_API_KEY or GOOGLE_API_KEY
GEMINI_API_KEY = _env("GEMINI_API_KEY") or GOOGLE_API_KEY
TAVILY_API_KEY = _env("TAVILY_API_KEY")

# --- Product ---
PRODUCT_URL = _env("PRODUCT_URL")

# --- Gemini ---
GEMINI_MODEL = _env("GEMINI_MODEL") or "gemini-2.0-flash"
GEMINI_BATCH_DELAY = _env_float("GEMINI_BATCH_DELAY", 3.0)
SKIP_GEMINI_ANALYSIS = _env_bool("SKIP_GEMINI_ANALYSIS")

# --- Scraping ---
SKIP_APIFY = _env_bool("SKIP_APIFY")


def get_skip_apify() -> bool:
    """Runtime check: respects os.environ override (e.g. from pipeline job)."""
    return os.environ.get("SKIP_APIFY", "").lower() in ("1", "true", "yes") or SKIP_APIFY


APIFY_AMAZON_ACTOR_ID = _env("APIFY_AMAZON_ACTOR_ID") or "delicious_zebu/amazon-product-details-scraper"

# --- Cache ---
CREATIVE_RESEARCH_NO_CACHE = _env_bool("CREATIVE_RESEARCH_NO_CACHE")

# --- MCP ---
CREATIVE_RESEARCH_MCP_HTTP = _env_bool("CREATIVE_RESEARCH_MCP_HTTP")

# --- API (for test script) ---
API_BASE_URL = _env("API_BASE_URL") or "http://localhost:8000"

# --- Project paths ---
PROJECT_ROOT = _PROJECT_ROOT

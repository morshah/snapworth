"""Runtime configuration, loaded from environment variables (.env in dev).

All third-party integrations require API keys. Missing keys are surfaced to
the caller as a clear 503 (see services.py) rather than crashing.
"""
import os

from dotenv import load_dotenv

load_dotenv()  # loads backend/.env if present; real env vars take precedence

# Authentication — HS256 JWT signing. Generate a secret with:
#   python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# Database — Postgres in production; defaults to a local SQLite file for dev.
# Set DATABASE_URL to your Neon/Supabase connection string to use Postgres.
DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"sqlite+aiosqlite:///{os.path.join(os.path.dirname(__file__), 'app.db')}"
)

# Reverse image search — SerpApi (Google Lens engine). https://serpapi.com
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

# Image hosting — SerpApi Google Lens needs a publicly reachable image URL,
# so locally-uploaded files are first hosted on imgbb. https://api.imgbb.com
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

# Report synthesis — Anthropic Claude. https://console.anthropic.com
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")

# Tunables
MAX_LISTINGS = int(os.getenv("MAX_LISTINGS", "5"))
MAX_IMAGES = int(os.getenv("MAX_IMAGES", "12"))
SCRAPE_TIMEOUT_SECONDS = float(os.getenv("SCRAPE_TIMEOUT_SECONDS", "8"))

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

# The JWT is delivered as an httpOnly cookie (not readable by JS → XSS-safe).
# COOKIE_SECURE must be True in production (HTTPS); keep False for local http dev.
COOKIE_NAME = "access_token"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")  # lax | strict | none

# Invitations (invite-only registration).
INVITE_EXPIRE_DAYS = int(os.getenv("INVITE_EXPIRE_DAYS", "7"))

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

# Tunables (pipeline thresholds)
MAX_FOUND_SITES = int(os.getenv("MAX_FOUND_SITES", "30"))   # sites recorded from search
MAX_LISTINGS = int(os.getenv("MAX_LISTINGS", "5"))          # sites actually visited/scraped
MAX_IMAGES = int(os.getenv("MAX_IMAGES", "12"))             # images aggregated into a report
SCRAPE_TIMEOUT_SECONDS = float(os.getenv("SCRAPE_TIMEOUT_SECONDS", "8"))

# Rate limiting (slowapi). Storage defaults to in-memory (per-process); set a
# shared backend (e.g. redis://host:6379) for multi-instance deployments.
RATE_LIMIT_STORAGE_URI = os.getenv("RATE_LIMIT_STORAGE_URI")
LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "5/minute")       # per IP
UPLOAD_RATE_LIMIT = os.getenv("UPLOAD_RATE_LIMIT", "10/hour")      # per user

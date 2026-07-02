# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Product Sourcing Intelligence Agent: a logged-in user uploads a product image → reverse image search finds matching listings → the top listings are scraped in parallel → an LLM synthesizes an intelligence report → the report is saved to the user's history. It is a **two-process app** split into `backend/` (Python/FastAPI) and `frontend/` (Next.js/React), each self-contained and run separately.

All three external integrations are **real** (no longer mocked): SerpApi (Google Lens) for reverse image search, imgbb for image hosting, and Anthropic Claude for report generation. Requests are JWT-authenticated and results are persisted to a database.

## Running

Backend (FastAPI) — from `backend/`, with the venv and a populated `.env`:
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload    # serves http://127.0.0.1:8000, Swagger UI at /docs
```

Frontend (Next.js) — from `frontend/`:
```bash
cd frontend
npm run dev                  # serves http://localhost:3000
npm run build                # production build
npm run lint                 # eslint via next lint
```

Both must run simultaneously. The frontend hardcodes the backend URL as `API_BASE_URL` in `frontend/components/ImageUploadForm.js` and `frontend/components/AuthForm.js` — change it in both if the backend host/port changes.

**Config lives in `backend/.env`** (copy from `.env.example`). Required for a full run: `SERPAPI_API_KEY`, `IMGBB_API_KEY`, `ANTHROPIC_API_KEY`, `JWT_SECRET`. Optional: `DATABASE_URL` (defaults to a local SQLite file). A missing service key returns a `503` naming the variable, so the app runs and tells you what to configure.

**`.env` is read at import time** — after editing it, **restart uvicorn** (`--reload` reacts to `.py` edits, not `.env` changes).

There is no automated test suite. Exercise endpoints via `/docs`, or the frontend.

## Architecture

### Module map (`backend/`)

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app, CORS, route handlers, and the `/upload-image` orchestration. Includes the auth router; DB tables are created on startup via a `lifespan` hook. |
| `auth.py` | JWT auth: `POST /register`, `POST /login`, and the `get_current_user` dependency. bcrypt hashing, HS256 tokens. |
| `db.py` | Async SQLAlchemy engine, `User`/`Report` ORM models, session dependency, `init_models()`, and Postgres-URL normalization. |
| `services.py` | The three external integrations (see below). Missing API keys raise `HTTPException(503)`. |
| `models.py` | Pydantic request/response models (API contract). Distinct from the SQLAlchemy ORM models in `db.py`. |
| `config.py` | Env-var loading (`python-dotenv`). |

### `/upload-image` request flow

Driven by `main.py:upload_image`, which depends on `auth.get_current_user` (401 without a valid Bearer JWT):

1. Save the uploaded image to `/tmp` under a UUID filename (cleaned up in `finally`).
2. `services.reverse_image_search` → hosts the image on imgbb, then queries SerpApi Google Lens → normalized listing dicts (`title`, `source`, `link`, `price`, `thumbnail`).
3. **Soft-error rule:** fewer than 3 listings → `HTTPException(400)`. This is the primary business rule to preserve.
4. Slice to the top `MAX_LISTINGS` (5), then scrape them concurrently via `asyncio.gather` (best-effort — failures degrade gracefully).
5. Aggregate images (search thumbnails + scraped `og:image`), capped at `MAX_IMAGES` (12); dedupe pdf/video links.
6. `services.generate_ai_report` → Claude synthesizes an `AIReport`.
7. Persist a `Report` row for the user (best-effort — a DB failure logs and still returns the report, so an expensive result isn't lost).
8. Return a `ProductIntelligenceReport`.

### External services (`services.py`)

Each is an isolated `async` function; all require an API key (else `503`):
- `host_image(path)` — uploads to **imgbb**, returns a public URL. Needed because SerpApi Google Lens fetches the image **by URL**, so a local `/tmp` file must be hosted first.
- `reverse_image_search(path)` — **SerpApi** `engine=google_lens`. Real thumbnails come straight from Google, so images actually render.
- `scrape_listing(url)` — **httpx + BeautifulSoup**, best-effort (many retailers block bots/JS-render). Always returns a dict with `images`/`pdf_links`/`video_links`; on any error returns an empty-ish dict.
- `generate_ai_report(listings, scraped)` — **Anthropic Claude** (`claude-opus-4-8` by default, `CLAUDE_MODEL` to override). Prompts for a JSON object and parses it into `AIReport`.

### Auth (`auth.py`)

- `POST /register` (username ≥3, password ≥8) and `POST /login` return `{access_token}` (HS256 JWT, `JWT_EXPIRE_MINUTES` = 60). Duplicate user → 409; bad creds → 401.
- Passwords hashed with **bcrypt**, run via `asyncio.to_thread` so the CPU-bound hash doesn't block the event loop.
- `get_current_user` decodes the Bearer token and loads the `User` ORM row (401 on missing/expired/invalid). Protected routes depend on it.
- Frontend stores the token in `localStorage` and sends `Authorization: Bearer …`; a `401` triggers auto-logout.

### Persistence (`db.py`)

- **Async SQLAlchemy 2.0.** `DATABASE_URL` selects the backend: unset → local `sqlite+aiosqlite` file (`app.db`); `postgres://…` → normalized to `postgresql+asyncpg` (and `sslmode` lifted out of the query into `connect_args={"ssl": True}`, since asyncpg rejects it in the URL).
- Report payloads use **JSONB on Postgres, JSON on SQLite** via a type variant, so the same models work on both.
- `Report` stores `user_id`, `preview_image_url`, `listings` (raw SerpApi matches), and `report` (the full `ProductIntelligenceReport` dump).
- History endpoints: `GET /reports` (list, newest first) and `GET /reports/{id}` (full, ownership-checked → 404 otherwise).
- Schema is created with `Base.metadata.create_all` on startup — this **only creates missing tables**, it does not migrate. Adopt Alembic before evolving the schema on real data.

### Frontend↔backend contract

The response shape is the Pydantic `ProductIntelligenceReport` / `AIReport`. The frontend renders directly against these field names (`report.summary`, `report.features_list`, `report.specs`, `report.pricing_summary`, `report.recommendation_sentiment`, `images`, `pdf_links`, `video_links`) — **changing a model field is a breaking change to `frontend/components/ImageUploadForm.js` and vice versa.** A saved report from `GET /reports/{id}` returns the same shape nested under `report`.

## Notes

- **Every upload costs money** — one SerpApi search + Claude tokens (and imgbb hosting). There is no caching of identical searches.
- **The pipeline is slow (~20–40s).** Reloading uvicorn (e.g. saving a `.py` file) mid-request drops the connection → the browser shows "Failed to fetch". Retry once the server is idle.
- **`sslmode`**: remove it from `DATABASE_URL` for a local Postgres (no SSL); keep `?sslmode=require` for managed Postgres (Neon/Supabase) — the normalizer handles it.
- **Secrets & DB are gitignored**: `.env` (all keys) and `*.db` (the SQLite user/report store). `.env.example` is the committed template.
- Frontend is plain Next.js `pages/` router (not App Router); global CSS in `frontend/styles/globals.css`, loaded via `pages/_app.js`.
- The two folders are independent (no root workspace tooling) — they communicate only over HTTP.
- Python deps are pinned in `backend/requirements.txt`. Recreate the venv with `cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.

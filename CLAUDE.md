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

Both must run simultaneously. The backend URL (`API_BASE_URL = http://localhost:8000`) and the shared `fetch` wrapper live in `frontend/lib/api.js` — change it there if the backend host/port changes. **Load the frontend from `http://localhost:3000` (not `127.0.0.1:3000`)** — the auth cookie is `SameSite=Lax`, so frontend and backend must share the `localhost` site or the cookie won't be sent.

**Config lives in `backend/.env`** (copy from `.env.example`). Required for a full run: `SERPAPI_API_KEY`, `IMGBB_API_KEY`, `ANTHROPIC_API_KEY`, `JWT_SECRET`. Optional: `DATABASE_URL` (defaults to a local SQLite file). A missing service key returns a `503` naming the variable, so the app runs and tells you what to configure.

**`.env` is read at import time** — after editing it, **restart uvicorn** (`--reload` reacts to `.py` edits, not `.env` changes).

**Before the first run on a fresh DB** (or after pulling new migrations), apply the schema from `backend/`: `alembic upgrade head`.

There is no automated test suite. Exercise endpoints via `/docs`, or the frontend.

## Architecture

### Module map (`backend/`)

| File | Responsibility |
|---|---|
| `main.py` | FastAPI app, CORS, route handlers, and the `/upload-image` orchestration. Includes the auth router. |
| `auth.py` | Cookie-based JWT auth: `POST /register`, `POST /login`, `POST /logout`, `GET /me`, and the `get_current_user` dependency. bcrypt hashing, HS256 tokens. |
| `db.py` | Async SQLAlchemy engine, `User`/`Report` ORM models, session dependency, and Postgres-URL normalization. |
| `services.py` | The three external integrations (see below). Missing API keys raise `HTTPException(503)`. |
| `models.py` | Pydantic request/response models (API contract). Distinct from the SQLAlchemy ORM models in `db.py`. |
| `config.py` | Env-var loading (`python-dotenv`). |
| `ratelimit.py` | slowapi limiter + the per-user/per-IP key function and 429 handler. |
| `admin.py` | Admin-only router (gated by `require_admin`): invitation CRUD and user management. |
| `make_admin.py` | One-off script to promote an existing user to admin (bootstraps the first admin). |

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

### Access model: invite-only

Registration is **invite-only** — there is no open sign-up. Flow: an admin creates an invitation (`POST /invitations`) → gets a single-use token → shares the link `/invite/<token>` → the invitee sets a username/password (`POST /register` with the token) → the invite is marked accepted (single-use, and expires after `INVITE_EXPIRE_DAYS`). An invite can `grants_admin` to mint another admin.

**Bootstrap:** the first admin is chicken-and-egg (only admins can invite, and registration needs an invite). Break it with `python make_admin.py <username>` on an already-registered account.

### Auth (`auth.py`) — httpOnly cookies

- `POST /register` (invite-gated: requires a valid, unused, unexpired `token`; username ≥3, password ≥8) and `POST /login` set the HS256 JWT (`JWT_EXPIRE_MINUTES` = 60) in an **httpOnly cookie** (`access_token`) and return `{username, is_admin}` — **the token is never in the response body**, so JS/XSS can't read it. Duplicate user → 409; bad creds → 401; bad/expired invite → 400.
- `GET /invite/{token}` (public) reports whether an invite is still valid — used by the accept page before showing the form.
- `POST /logout` clears the cookie (JS can't); `GET /me` returns the current user (the frontend calls it on load to learn whether it's authenticated, since it can't read the cookie).
- Passwords hashed with **bcrypt** via `asyncio.to_thread` (keeps the CPU-bound hash off the event loop).
- `get_current_user` reads the token from the **cookie first, then an `Authorization: Bearer` header** (so Swagger/API clients still work), verifies it, and loads the `User` ORM row (401 otherwise). Protected routes depend on it.
- **Cross-origin cookie constraint:** the cookie is `SameSite=Lax`, so the frontend and backend must be the **same site**. The frontend calls `http://localhost:8000` (not `127.0.0.1`) so it's same-site with `localhost:3000`. CORS has `allow_credentials=True` and specific origins (not `*`). `COOKIE_SECURE` must be `True` in production (HTTPS); `False` for local http. Frontend fetches all use `credentials: 'include'` and send **no** `Authorization` header.
- **CSRF:** `SameSite=Lax` blocks the cookie on cross-site POSTs, which mitigates CSRF here. For a real cross-site production setup, add CSRF tokens (or keep everything same-site).

### Admin & user management (`admin.py`)

- Gated by the `require_admin` dependency (403 for non-admins), applied at the router level.
- **Invitations:** `POST /invitations` (create, returns token), `GET /invitations` (list), `DELETE /invitations/{id}` (revoke).
- **Users:** `GET /users` (list), `PATCH /users/{id}` (toggle `is_admin` and/or reset password), `DELETE /users/{id}` (deletes the user and their reports — reports FK-reference the user, so they're removed first).
- **Self-lockout guards:** an admin can't remove their own admin flag or delete their own account (400).

### Rate limiting (`ratelimit.py`)

- **slowapi.** `/login` and `/register` are limited **per IP** (`LOGIN_RATE_LIMIT`, default `5/minute`) for brute-force protection; `/upload-image` is limited **per user** (`UPLOAD_RATE_LIMIT`, default `10/hour`) for cost protection — each upload spends money.
- The limiter is registered on `app.state.limiter` with a custom 429 handler returning `{"detail": ...}` (matches the rest of the API). Rate-limited routes take a `request: Request` param (slowapi requirement).
- The per-user key (`user_or_ip`) reads the JWT subject from the cookie/header, falling back to client IP.
- Storage is **in-memory (per-process)** by default — set `RATE_LIMIT_STORAGE_URI` (e.g. `redis://…`) for a multi-instance deployment, or limits won't be shared across workers.
- **Note:** `get_current_user` (a dependency) runs before the limiter on `/upload-image`, so unauthenticated calls get `401` and aren't counted against the per-user limit — fine, since only authenticated calls cost money.

### Persistence (`db.py`)

- **Async SQLAlchemy 2.0.** `DATABASE_URL` selects the backend: unset → local `sqlite+aiosqlite` file (`app.db`); `postgres://…` → normalized to `postgresql+asyncpg` (and `sslmode` lifted out of the query into `connect_args={"ssl": True}`, since asyncpg rejects it in the URL).
- Report payloads use **JSONB on Postgres, JSON on SQLite** via a type variant, so the same models work on both.
- `Report` stores `user_id`, `preview_image_url`, `listings` (raw SerpApi matches), and `report` (the full `ProductIntelligenceReport` dump).
- History endpoints: `GET /reports` (list, newest first) and `GET /reports/{id}` (full, ownership-checked → 404 otherwise).

### Migrations (Alembic)

Schema is managed by **Alembic** — the app no longer auto-creates tables. Config lives in `backend/`; run all commands from there with the venv active.

- `alembic/env.py` reuses `db.engine` and `db.Base.metadata`, so migrations use the same `DATABASE_URL` and SSL handling as the app (no URL duplicated in `alembic.ini`).
- **Apply migrations:** `alembic upgrade head` (required on a fresh DB before first run).
- **After changing a model in `db.py`:** `alembic revision --autogenerate -m "describe change"`, review the generated file in `alembic/versions/`, then `alembic upgrade head`.
- `compare_type=True` is on, so column-type changes are detected. Always eyeball autogenerated migrations — Alembic can miss renames and some constraint changes.
- Cross-dialect gotcha: JSON columns use `sa.JSON().with_variant(postgresql.JSONB(...), "postgresql")` so one migration works on both Postgres (JSONB) and SQLite (JSON). Keep that pattern for new JSON columns.

### Frontend↔backend contract

The response shape is the Pydantic `ProductIntelligenceReport` / `AIReport`. The frontend renders directly against these field names (`report.summary`, `report.features_list`, `report.specs`, `report.pricing_summary`, `report.recommendation_sentiment`, `images`, `pdf_links`, `video_links`) — **changing a model field is a breaking change to `frontend/components/SourcingView.js` and vice versa.** A saved report from `GET /reports/{id}` returns the same shape nested under `report`.

**Frontend structure:** `pages/index.js` → `App` (bootstraps auth via `/me`) → `AuthForm` (login-only) or `Dashboard` (nav + view switching: `SourcingView`, `UsersView`, `InvitationsView`; admin views only for admins). `pages/invite/[token].js` is the public invite-accept page. All API calls go through the `api()` helper in `lib/api.js` (`credentials: 'include'`). Auth state lives in `App`; views bubble a 401 up via `onAuthError` to return to login.

## Notes

- **Every upload costs money** — one SerpApi search + Claude tokens (and imgbb hosting). There is no caching of identical searches.
- **The pipeline is slow (~20–40s).** Reloading uvicorn (e.g. saving a `.py` file) mid-request drops the connection → the browser shows "Failed to fetch". Retry once the server is idle.
- **`sslmode`**: remove it from `DATABASE_URL` for a local Postgres (no SSL); keep `?sslmode=require` for managed Postgres (Neon/Supabase) — the normalizer handles it.
- **Secrets & DB are gitignored**: `.env` (all keys) and `*.db` (the SQLite user/report store). `.env.example` is the committed template.
- Frontend is plain Next.js `pages/` router (not App Router); global CSS in `frontend/styles/globals.css`, loaded via `pages/_app.js`.
- The two folders are independent (no root workspace tooling) — they communicate only over HTTP.
- Python deps are pinned in `backend/requirements.txt`. Recreate the venv with `cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.

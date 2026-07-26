# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Snapworth: a logged-in user uploads a product image → reverse image search finds matching listings → each top listing is visited, scraped, and AI-summarized → an LLM merges everything into a final report. It is a **two-process app** split into `backend/` (Python/FastAPI) and `frontend/` (Next.js/React), each self-contained and run separately.

All three external integrations are **real** (no longer mocked): SerpApi (Google Lens) for reverse image search, imgbb for image hosting, and Anthropic Claude for per-site + merged report generation. Access is invite-only and cookie-authenticated.

**Processing is asynchronous.** `POST /upload-image` creates a job row and returns immediately; a background task (`pipeline.py`) runs the pipeline and writes progress to the DB after every step. The frontend **polls** `GET /reports/{id}` and renders each step as it lands (sites found → each site visited → merged report). Because all progress lives in the DB, leaving the page and returning just re-reads current state — timers included.

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
| `pipeline.py` | The background job (`run`) — executes the pipeline and commits progress to the DB after each step. |
| `services.py` | The external integrations (see below). Missing API keys raise `HTTPException(503)`. |
| `storage.py` | Local per-product image storage (`storage/reports/{id}/site_{n}/…`) + path-traversal-safe resolution. Swappable for S3/R2. |
| `models.py` | Pydantic request/response models (API contract). Distinct from the SQLAlchemy ORM models in `db.py`. |
| `config.py` | Env-var loading (`python-dotenv`). |
| `ratelimit.py` | slowapi limiter + the per-user/per-IP key function and 429 handler. |
| `admin.py` | Admin-only router (gated by `require_admin`): invitation CRUD and user management. |
| `make_admin.py` | One-off script to promote an existing user to admin (bootstraps the first admin). |

### Job model & progressive pipeline

`POST /upload-image` (auth + per-user rate limit) saves the upload to `/tmp`, creates a `Report` row with `status="processing"`, spawns `asyncio.create_task(pipeline.run(id, path))`, and returns `{id}` immediately. Task refs are held in `main._jobs` so they aren't GC'd.

`pipeline.run` opens its **own** DB session and walks the status lifecycle, committing after each step so the poller sees incremental updates:

1. `status=searching`, `started_at` set. Host image on imgbb → `image_url` (the uploaded image).
2. `serpapi_lens(image_url)` → all found sites → `listings` (capped at `MAX_FOUND_SITES`).
3. **Soft-error rule:** fewer than 3 → `status=error` with the friendly message. Preserve this.
4. Seed `sites` = top `MAX_LISTINGS` as `pending`; `status=scraping`.
5. For each site: `status=visiting` → `scrape_listing` → `summarize_site` (per-site Claude summary) → `done`/`failed`, commit after each. One bad site doesn't kill the run.
6. `status=summarizing` → `generate_ai_report(sites)` merges all sites → `report` (a `MergedReport`).
7. `status=done`, `finished_at`. Any exception → `status=error` with the message. Temp file removed in `finally`.

**Mutable-JSON gotcha:** the `sites` column is mutated in place each loop; SQLAlchemy won't detect that, so `flag_modified(report, "sites")` is called before each commit. Don't remove it or per-site progress silently won't persist.

**Restart caveat:** jobs run in-process. If the server restarts mid-job, that report is stuck at its last-committed status. Acceptable for dev; a production version would use a durable queue and a startup sweep to fail orphaned `processing` rows.

### The report shape (`MergedReport`)

The merged report is framed as a **decision case for a sourcing manager**: `{ summary, features, specifications, pricing_summary, recommendation, pros (list), cons (list), customer_sentiment, manufacturer, barcodes, wholesalers }`. Per-site data (`SiteResult`) carries `summary`, `price`/`price_value`/`currency`, `description`, `manufacturer`, `seller`, `rating`/`rating_value`/`review_count`, `reviews`, `barcodes`, `specs`, `images` (served paths), `status`, timestamps. Both live inside JSON columns, so adding fields needs **no migration**.

`ReportStatus.stats` (`ReportStats`) is **computed on read** in `main._compute_stats` from the site data — sites found, sites with price, price min/max/median/Q1/Q3 + raw values (for the box plot), avg rating, total reviews. The frontend renders KPI cards + an SVG box plot (`PriceChart.js`) from it.

### External services (`services.py`)

Each is an isolated `async` function; all require an API key (else `503`):
- `host_image(path)` — uploads to **imgbb**, returns a public URL. Needed because SerpApi Google Lens fetches the image **by URL**, so a local `/tmp` file must be hosted first. The returned URL is also stored as the report's uploaded image.
- `serpapi_lens(image_url)` — **SerpApi** `engine=google_lens` on an already-hosted URL. Real thumbnails come straight from Google, so images actually render.
- `scrape_listing(url)` — **httpx + BeautifulSoup**, best-effort. Parses **JSON-LD/schema.org `Product`** first (images array, brand/manufacturer, GTIN/UPC/EAN barcodes, offer price + seller, rating, `additionalProperty` specs) with Open Graph / meta / `<img>` fallbacks. Returns `title`/`description`/`price`/`manufacturer`/`seller`/`rating`/`barcodes`/`specs`/`image_urls`. Anti-bot/JS sites (Amazon) still yield less without a scraping API.
- `fetch_image(url)` — downloads one image (skips non-images/tiny icons) for storage.
- `summarize_site(listing, scraped)` — small **Claude** call → a 2–3 sentence per-site summary over the rich data.
- `generate_ai_report(sites)` — **Claude** (`CLAUDE_MODEL`, default `claude-opus-4-8`) merges all site data into a `MergedReport` (adds merged `manufacturer`/`barcodes`/`wholesalers`).

**Image storage:** the pipeline downloads up to `MAX_IMAGES_PER_SITE` images per site via `fetch_image`, saves them under `storage/reports/{id}/site_{n}/` (`storage.py`), and records **served endpoint paths** (`/reports/{id}/images/{n}/{file}`) on the site result — never public URLs. `GET /reports/{id}/images/{site}/{file}` serves them **only to the report's owner** (auth cookie + ownership check); `storage.image_path` rejects path traversal. The `storage/` dir is gitignored. For production, swap `storage.py` for S3/R2 + presigned URLs.

Thresholds are all env-configurable: `MAX_FOUND_SITES`, `MAX_LISTINGS`, `MAX_IMAGES`, `MAX_IMAGES_PER_SITE`, `SCRAPE_TIMEOUT_SECONDS`, `STORAGE_DIR`.

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
- `Report` is the job row: `status`, `image_url` (uploaded image), `listings` (all found sites), `sites` (per-site visited results), `report` (final `MergedReport`, null until done), `error`, and `started_at`/`finished_at`. **Everything the pipeline finds is persisted** — found sites, each visited site's data + summary, and the merged report + uploaded image.
- Endpoints: `GET /reports` (grid of the user's uploads with status + timer fields), `GET /reports/{id}` (full live state — the **polling** endpoint; ownership-checked → 404 otherwise).

### Migrations (Alembic)

Schema is managed by **Alembic** — the app no longer auto-creates tables. Config lives in `backend/`; run all commands from there with the venv active.

- `alembic/env.py` reuses `db.engine` and `db.Base.metadata`, so migrations use the same `DATABASE_URL` and SSL handling as the app (no URL duplicated in `alembic.ini`).
- **Apply migrations:** `alembic upgrade head` (required on a fresh DB before first run).
- **After changing a model in `db.py`:** `alembic revision --autogenerate -m "describe change"`, review the generated file in `alembic/versions/`, then `alembic upgrade head`.
- `compare_type=True` is on, so column-type changes are detected. Always eyeball autogenerated migrations — Alembic can miss renames and some constraint changes.
- Cross-dialect gotcha: JSON columns use `sa.JSON().with_variant(postgresql.JSONB(...), "postgresql")` so one migration works on both Postgres (JSONB) and SQLite (JSON). Keep that pattern for new JSON columns.

### Frontend↔backend contract

`GET /reports/{id}` returns a `ReportStatus`: `status`, `image_url`, `found_sites`, `sites` (each `SiteResult`), `report` (`MergedReport` or null), plus timestamps. The frontend renders against these names — **changing a model field is a breaking change to `frontend/components/ProductDetail.js` and vice versa.** The final report fields are `summary`, `features`, `specifications`, `pricing_summary`, `recommendation`.

**Frontend structure:** `pages/index.js` → `App` (bootstraps auth via `/me`) → `AuthForm` (login-only) or `Dashboard` (nav: `SourcingView`, `UsersView`, `InvitationsView`; admin views only for admins). `SourcingView` = upload + products grid; clicking a product opens `ProductDetail`, which **polls** `GET /reports/{id}` every 1.5s while active and renders progress (found sites → collapsible per-site cards with live timers → merged report). `pages/invite/[token].js` is the public invite-accept page. Shared helpers: `lib/api.js` (fetch + cookie), `lib/status.js` (lifecycle), `lib/time.js` (`useNow`/`elapsed`/`formatDuration` — timers derive from server `started_at`, so they're correct across navigation). Auth state lives in `App`; views bubble a 401 up via `onAuthError`.

## Notes

- **Every upload costs money** — one SerpApi search + Claude tokens (and imgbb hosting). There is no caching of identical searches.
- **The pipeline is slow (~20–40s).** Reloading uvicorn (e.g. saving a `.py` file) mid-request drops the connection → the browser shows "Failed to fetch". Retry once the server is idle.
- **`sslmode`**: remove it from `DATABASE_URL` for a local Postgres (no SSL); keep `?sslmode=require` for managed Postgres (Neon/Supabase) — the normalizer handles it.
- **Secrets & DB are gitignored**: `.env` (all keys) and `*.db` (the SQLite user/report store). `.env.example` is the committed template.
- Frontend is plain Next.js `pages/` router (not App Router); global CSS in `frontend/styles/globals.css`, loaded via `pages/_app.js`.
- The two folders are independent (no root workspace tooling) — they communicate only over HTTP.
- Python deps are pinned in `backend/requirements.txt`. Recreate the venv with `cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.

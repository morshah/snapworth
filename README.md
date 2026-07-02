# Product Sourcing Intelligence Agent

A full-stack app where a logged-in user uploads a product image, and the system performs a **reverse image search** to find matching listings online, **scrapes** those listings, and uses an **AI model** to synthesize a single, unbiased product intelligence report. Each report is saved to the user's history.

## Technical Stack

* **Backend:** Python, FastAPI, SQLAlchemy (async), Alembic (migrations)
* **Frontend:** React / Next.js
* **Database:** PostgreSQL (production) / SQLite (local dev)
* **External APIs:** SerpApi (Google Lens), imgbb (image hosting), Anthropic Claude
* **Auth:** JWT (PyJWT) + bcrypt password hashing

## Features

Everything built so far:

### Accounts & Security
* **Invite-only access** — no open sign-up. New users can only register through a single-use, expiring **invitation link** created by an admin. Passwords hashed with **bcrypt**.
* **Login** — `POST /login` verifies credentials and issues a signed **JWT** (HS256, 60-min expiry).
* **httpOnly cookie auth** — the JWT is stored in an **httpOnly, SameSite=Lax cookie** (never exposed to JavaScript, so XSS can't steal it). `POST /logout` clears it; `GET /me` returns the current user.
* **Protected API** — `/upload-image` and the report endpoints require the auth cookie; unauthenticated requests get `401`.
* **Rate limiting** — `/login` & `/register` are throttled per IP (default 5/min, brute-force protection); `/upload-image` is throttled per user (default 10/hour, cost protection). Returns `429` when exceeded.
* **Frontend auth gate** — login screen in front of the app; auth state comes from `GET /me`, auto-logout on session expiry.

### Admin Dashboard
* **Dashboard with nav** — signed-in users get a nav; admins additionally see **Users** and **Invitations** tabs.
* **Invitations** — admins create invite links (with an optional email note and an "admin" flag), copy the link to send manually, and revoke pending invites. Invites are single-use and expire (default 7 days).
* **User management** — admins list users, grant/revoke admin, reset passwords, and delete users. Self-lockout is prevented (you can't demote or delete yourself).
* **Invite-accept page** — invitees open `/invite/<token>` to set their username and password.

### Core Pipeline
* **Image upload** — accepts a multipart/form-data image file.
* **Image hosting (imgbb)** — uploads the image to get a public URL (required because Google Lens fetches the image by URL); this is also stored as the product's uploaded image.
* **Reverse image search (SerpApi / Google Lens)** — finds matching product listings, with real product titles, sources, prices, and thumbnails.
* **Web scraping (httpx + BeautifulSoup)** — best-effort scrape of each visited listing for detail (description, price, image); degrades gracefully when a site blocks scraping.
* **Per-site AI summaries** — a Claude call summarizes each visited listing as it's processed.
* **Merged AI report (Anthropic Claude)** — merges all sites into one report: `summary`, `features`, `specifications`, `pricing_summary`, `recommendation`.
* **Configurable thresholds** — number of sites to record/visit, images to fetch, and scrape timeout are all set in `.env`.
* **Soft error handling** — if fewer than 3 matches are found, the job ends with a friendly error.

### Live Progress (async processing)
* **Instant start** — uploading kicks off a background job and returns immediately; the UI shows each step as it completes rather than waiting for the whole pipeline.
* **Step-by-step results** — see the list of all sites found, then each site as it's visited (with what was found + its AI summary), then the final merged report.
* **Live timers** — an overall timer and a per-site timer show elapsed time; the current site expands while older ones collapse to a one-line origin.
* **Survives navigation** — all progress is stored server-side, so leaving the page and coming back (or refreshing) resumes exactly where it is, timers included.
* **Products grid** — a grid of all your uploads, each with its status and a live timer for in-progress ones; click any product to open its progress/report.

### Persistence & History
* **Everything is saved** — the uploaded image, all sites found, each visited site's data + summary, and the final merged report are persisted (PostgreSQL/SQLite via SQLAlchemy; JSONB on Postgres).
* **Endpoints** — `GET /reports` (grid list), `GET /reports/{id}` (full live state, ownership-checked). Past products re-open instantly without re-running the (paid) pipeline.
* **Versioned schema migrations (Alembic)** — schema changes are tracked as migration files, applied with `alembic upgrade head` (no manual SQL).

## External APIs & Keys

The pipeline calls three third-party services. Each needs an API key in `backend/.env`:

| Service | Purpose | Get a key | Cost |
|---|---|---|---|
| **Anthropic Claude** | Generates the report | https://console.anthropic.com/settings/keys | Pay-per-token (cents per report) |
| **SerpApi** | Reverse image search (Google Lens) | https://serpapi.com | Free tier (~100 searches/mo), then paid |
| **imgbb** | Hosts the uploaded image for SerpApi | https://api.imgbb.com | Free |

> ⚠️ **Each upload spends real money** (one SerpApi search + Claude tokens). There is no caching of identical searches.

## Project Structure

Two self-contained apps that communicate over HTTP:

```
backend/                 FastAPI service
  main.py                app + routes + /upload-image orchestration
  auth.py                login / invite-gated register / cookie + JWT dependency
  admin.py               admin-only: invitation + user management
  make_admin.py          bootstrap script: create/promote an admin
  ratelimit.py           slowapi rate limiting
  db.py                  async SQLAlchemy engine + User/Report/Invitation models
  services.py            SerpApi + imgbb + scraping + Claude integrations
  models.py              Pydantic request/response models
  config.py              env-var loading
  alembic/               database migrations (versions/, env.py)
  alembic.ini            Alembic config
  requirements.txt
  .env.example           template — copy to .env and fill in
frontend/                Next.js app
  pages/                 index.js, _app.js, invite/[token].js
  components/            App, AuthForm, Dashboard, SourcingView, UsersView, InvitationsView
  lib/api.js             fetch wrapper (sends the auth cookie)
  styles/globals.css
  package.json
```

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in the keys below
```

Edit `backend/.env`:

| Variable | Required | Notes |
|---|---|---|
| `SERPAPI_API_KEY` | yes | Reverse image search |
| `IMGBB_API_KEY` | yes | Image hosting |
| `ANTHROPIC_API_KEY` | yes | Report generation |
| `JWT_SECRET` | yes | Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | no | Postgres URL (see below). Unset → local SQLite file. |
| `CLAUDE_MODEL` | no | Defaults to `claude-opus-4-8` |
| `JWT_EXPIRE_MINUTES` | no | Defaults to `60` |
| `COOKIE_SECURE` | no | `false` for local http; **set `true` in production (HTTPS)** |
| `LOGIN_RATE_LIMIT` | no | Defaults to `5/minute` (per IP) |
| `UPLOAD_RATE_LIMIT` | no | Defaults to `10/hour` (per user) |
| `RATE_LIMIT_STORAGE_URI` | no | In-memory by default; set e.g. `redis://…` for multi-instance |
| `INVITE_EXPIRE_DAYS` | no | Invite link lifetime; defaults to `7` |
| `MAX_FOUND_SITES` | no | Sites recorded from search; defaults to `30` |
| `MAX_LISTINGS` | no | Sites actually visited & scraped; defaults to `5` |
| `MAX_IMAGES` | no | Images aggregated per report; defaults to `12` |
| `SCRAPE_TIMEOUT_SECONDS` | no | Per-site scrape timeout; defaults to `8` |

Apply the database schema, create your first admin, then run the server:
```bash
alembic upgrade head                    # sets up / migrates the database
python make_admin.py <username>         # bootstrap the first admin (prompts for a password)
uvicorn main:app --reload
```
Backend serves `http://127.0.0.1:8000` (Swagger UI at `/docs`). Registration is invite-only, so the first admin must be created with `make_admin.py`; after that, all other users join via invite links from the dashboard.

> After editing `.env`, **restart uvicorn** — env vars are read at startup, not on `--reload`.

### 2. Database

* **Local dev (default):** leave `DATABASE_URL` unset — the app uses a local SQLite file (`backend/app.db`). Zero setup.
* **PostgreSQL:** create a database, then set:
  ```
  # local Postgres (no SSL):
  DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
  # managed Postgres (Neon/Supabase — keep sslmode):
  DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require
  ```
  No code changes needed — the app normalizes the URL. Run `alembic upgrade head` to create the tables.

### Database migrations (Alembic)

The schema is managed by **Alembic** (run from `backend/` with the venv active):

```bash
alembic upgrade head                              # apply all migrations
alembic revision --autogenerate -m "add x"        # after editing a model in db.py
alembic downgrade -1                              # roll back one migration
```

After autogenerating a migration, review the file in `backend/alembic/versions/` before applying it. Migrations reuse the app's `DATABASE_URL`, so they target whichever database `.env` points at.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```
Frontend serves `http://localhost:3000`.

## Usage

1. Start both backend and frontend.
2. Open **`http://localhost:3000`** and **log in** as your admin account. Use `localhost` (not `127.0.0.1`) — the auth cookie requires the frontend and backend to share the `localhost` site.
3. **To add users:** go to the **Invitations** tab → create an invite → **Copy link** → send it to the new user. They open it, set a password, and they're in. Manage users (roles, delete) in the **Users** tab.
4. Choose a product image and click **Upload & Get Report**.
5. The pipeline runs (~20–40s) and renders the report with real product images. It's saved under **Recent reports** — click any past entry to re-view it.

## Notes & Roadmap

* **Production hardening:** set `COOKIE_SECURE=true` (requires HTTPS). The `SameSite=Lax` cookie mitigates CSRF for same-site use; a cross-site production frontend would need CSRF tokens. Rate-limit storage is in-memory — use `RATE_LIMIT_STORAGE_URI` (Redis) if you run more than one backend instance.
* **Background jobs run in-process:** if the backend restarts mid-job, that report stays at its last-saved step. Fine for single-instance dev/MVP; a production version would move processing to a durable queue (Celery/RQ/Arq) and fail orphaned jobs on startup.
* `.env` and the SQLite DB (`*.db`) are gitignored; never commit real keys.

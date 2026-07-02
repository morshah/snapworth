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
* **User registration** — `POST /register` creates an account (username ≥3 chars, password ≥8), passwords hashed with **bcrypt**.
* **Login** — `POST /login` verifies credentials and issues a signed **JWT** (HS256, 60-min expiry).
* **httpOnly cookie auth** — the JWT is stored in an **httpOnly, SameSite=Lax cookie** (never exposed to JavaScript, so XSS can't steal it). `POST /logout` clears it; `GET /me` returns the current user.
* **Protected API** — `/upload-image` and the report endpoints require the auth cookie; unauthenticated requests get `401`.
* **Rate limiting** — `/login` & `/register` are throttled per IP (default 5/min, brute-force protection); `/upload-image` is throttled per user (default 10/hour, cost protection). Returns `429` when exceeded.
* **Frontend auth gate** — login/register screen in front of the app; auth state comes from `GET /me`, auto-logout on session expiry.

### Core Pipeline
* **Image upload** — accepts a multipart/form-data image file.
* **Image hosting (imgbb)** — uploads the image to get a public URL (required because Google Lens fetches the image by URL).
* **Reverse image search (SerpApi / Google Lens)** — finds matching product listings, with real product titles, sources, prices, and thumbnails.
* **Parallel web scraping (httpx + BeautifulSoup)** — best-effort scrape of the top listings for extra detail (description, price, og:image, PDF links); degrades gracefully when a site blocks scraping.
* **AI report generation (Anthropic Claude)** — synthesizes the gathered data into a structured, unbiased report using `claude-opus-4-8`.
* **Structured output** — returns a JSON object: `report` (summary, features list, specs, pricing summary, recommendation), aggregated `images`, and `pdf_links` / `video_links`.
* **Soft error handling** — if fewer than 3 matches are found, returns a `400` asking for a clearer photo.

### Persistence & History
* **Report persistence** — every completed search is saved to the database (PostgreSQL/SQLite via SQLAlchemy; report payload stored as JSONB on Postgres).
* **Report history** — `GET /reports` lists a user's past reports (newest first); `GET /reports/{id}` returns a full saved report (ownership-checked).
* **History UI** — a "Recent reports" panel lists past searches with thumbnails; click one to re-view it instantly without re-running the (paid) pipeline.
* **Versioned schema migrations (Alembic)** — database schema changes are tracked as migration files, applied with `alembic upgrade head` (no manual SQL).

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
  auth.py                register / login / JWT dependency
  db.py                  async SQLAlchemy engine + User/Report models
  services.py            SerpApi + imgbb + scraping + Claude integrations
  models.py              Pydantic request/response models
  config.py              env-var loading
  alembic/               database migrations (versions/, env.py)
  alembic.ini            Alembic config
  requirements.txt
  .env.example           template — copy to .env and fill in
frontend/                Next.js app
  pages/                 index.js, _app.js
  components/            ImageUploadForm.js, AuthForm.js
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

Apply the database schema (creates the tables), then run the server:
```bash
alembic upgrade head          # sets up / migrates the database
uvicorn main:app --reload
```
Backend serves `http://127.0.0.1:8000` (Swagger UI at `/docs`).

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
2. Open **`http://localhost:3000`** → **register** an account (or log in). Use `localhost` (not `127.0.0.1`) — the auth cookie requires the frontend and backend to share the `localhost` site.
3. Choose a product image and click **Upload & Get Report**.
4. The pipeline runs (~20–40s) and renders the report with real product images. It's saved under **Recent reports** — click any past entry to re-view it.

## Notes & Roadmap

* **Production hardening:** set `COOKIE_SECURE=true` (requires HTTPS). The `SameSite=Lax` cookie mitigates CSRF for same-site use; a cross-site production frontend would need CSRF tokens. Rate-limit storage is in-memory — use `RATE_LIMIT_STORAGE_URI` (Redis) if you run more than one backend instance.
* `.env` and the SQLite DB (`*.db`) are gitignored; never commit real keys.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Product Sourcing Intelligence Agent: upload an image → reverse image search → scrape the top matching product listings in parallel → synthesize an AI intelligence report. It is a **two-process app** — a Python/FastAPI backend and a Next.js/React frontend running separately. All three external integrations (vision API, web scraping, LLM report generation) are currently **mocked** in `main.py`; there is no real network I/O to third parties.

## Running

Backend (FastAPI) — from repo root, with the venv:
```bash
source venv/bin/activate
uvicorn main:app --reload    # serves http://127.0.0.1:8000, Swagger UI at /docs
```

Frontend (Next.js):
```bash
npm run dev                  # serves http://localhost:3000
npm run build                # production build
npm run lint                 # eslint via next lint
```

Both must run simultaneously. The frontend hardcodes the backend URL as `API_BASE_URL` in `components/ImageUploadForm.js` — change it there if the backend host/port changes.

There is no test suite. To exercise the backend directly, POST a multipart `file` field to `/upload-image` (e.g. via `/docs`).

## Architecture

Single request flow, driven entirely by `POST /upload-image` in `main.py:upload_image`:

1. Save the uploaded image to `/tmp` under a UUID filename (cleaned up in a `finally` block).
2. `call_reverse_image_api` → list of candidate product URLs.
3. **Soft-error rule:** fewer than 3 URLs → `HTTPException(400)` with a user-facing message. This is the primary business rule to preserve.
4. Slice to the top 5 URLs, then scrape them concurrently via `asyncio.gather([scrape_url(...) ...])`.
5. Aggregate results: images capped at 12 total across all listings; PDF/video links deduped via `set()`.
6. `generate_ai_report` synthesizes the scraped data into the structured report.
7. Return a `ProductIntelligenceReport`.

The response shape is defined by the Pydantic models `AIReport` and `ProductIntelligenceReport` (`main.py`). The frontend renders directly against these field names (`report.summary`, `report.features_list`, `report.specs`, `report.pricing_summary`, `report.recommendation_sentiment`, `images`, `pdf_links`, `video_links`) — **changing a model field is a breaking change to `ImageUploadForm.js` and vice versa.**

### The three mock seams

Replacing the mocks with real integrations is the expected direction of work. Each is an isolated `async` function in `main.py` with a docstring describing the real implementation:
- `call_reverse_image_api(image_path)` — Google Vision / Azure Computer Vision.
- `scrape_url(url)` — httpx + BeautifulSoup/Playwright. Must return a dict with `images`, `pdf_links`, `video_links` (plus `price`, `availability`, etc.) for the aggregation step to work.
- `generate_ai_report(scraped_data)` — OpenAI / Anthropic SDK; must return an `AIReport`.

### Mock-driven test triggers

Behavior is filename-driven so scenarios can be reproduced without real APIs:
- An uploaded filename containing `blurry_photo` (case-insensitive) → returns 2 URLs → triggers the <3-matches 400 error.
- Any other filename → returns 6 URLs → full report. `scrape_url` returns different canned data based on `store-a` / `store-b` / `store-c` substrings in the URL.

## Notes

- Frontend is plain Next.js `pages/` router (not App Router); no `src/` dir despite README mentioning it as optional.
- Python deps are pinned in `requirements.txt` (direct deps: fastapi, uvicorn, pydantic, python-multipart). Recreate the venv with `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.

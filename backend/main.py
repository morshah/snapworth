import asyncio
import os
import shutil
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import auth
import config
import db
import ratelimit
import services
from models import ProductIntelligenceReport, ReportListItem, StoredReport

# Schema is managed by Alembic — run `alembic upgrade head` (see README).
app = FastAPI(title="Product Sourcing Intelligence Agent")

# Rate limiting (slowapi): register the limiter and the 429 handler.
app.state.limiter = ratelimit.limiter
app.add_exception_handler(RateLimitExceeded, ratelimit.rate_limit_handler)

# Auth routes: POST /register and POST /login (issue JWTs).
app.include_router(auth.router)

# Allow the Next.js dev server (http://localhost:3000) to call this API from
# the browser. Without this, cross-origin fetches fail with "Failed to fetch".
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,  # required so the browser sends/stores the auth cookie
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload-image", response_model=ProductIntelligenceReport)
@ratelimit.limiter.limit(config.UPLOAD_RATE_LIMIT, key_func=ratelimit.user_or_ip)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    user: db.User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(db.get_session),
):
    """Upload an image → reverse image search → scrape listings → AI report.

    Protected: requires a valid Bearer JWT (obtain one via /login). The report
    is persisted to the user's history. Requires SERPAPI_API_KEY, IMGBB_API_KEY,
    and ANTHROPIC_API_KEY (see backend/.env.example).
    """
    # 1. Save the uploaded image to a unique temp path.
    file_extension = os.path.splitext(file.filename)[1]
    temp_image_path = f"/tmp/{uuid.uuid4().hex}{file_extension}"

    try:
        with open(temp_image_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. Reverse image search for matching product listings.
        listings = await services.reverse_image_search(temp_image_path)
        print(f"Found {len(listings)} matching listings")

        # 3. Business rule: fewer than 3 matches → soft error.
        if len(listings) < 3:
            raise HTTPException(
                status_code=400,
                detail="Less than 3 product matches found. Please try again with a clearer photo.",
            )

        top_listings = listings[: config.MAX_LISTINGS]

        # 4. Scrape the top listings in parallel (best-effort).
        scraped = await asyncio.gather(
            *(services.scrape_listing(item["link"]) for item in top_listings if item.get("link"))
        )

        # 5. Aggregate images (thumbnails from search + scraped og:images), capped.
        all_images: list[str] = []
        for item in top_listings:
            if item.get("thumbnail") and len(all_images) < config.MAX_IMAGES:
                all_images.append(item["thumbnail"])
        for result in scraped:
            for img_url in result.get("images", []):
                if len(all_images) < config.MAX_IMAGES:
                    all_images.append(img_url)

        all_pdf_links: list[str] = []
        all_video_links: list[str] = []
        for result in scraped:
            all_pdf_links.extend(result.get("pdf_links", []))
            all_video_links.extend(result.get("video_links", []))

        # 6. Synthesize the report with Claude.
        ai_report = await services.generate_ai_report(top_listings, list(scraped))

        result = ProductIntelligenceReport(
            report=ai_report,
            images=all_images,
            pdf_links=list(dict.fromkeys(all_pdf_links)),
            video_links=list(dict.fromkeys(all_video_links)),
        )

        # 7. Persist to the user's history. A storage hiccup shouldn't lose the
        #    (expensive) report the user just paid for, so log and continue.
        try:
            session.add(
                db.Report(
                    user_id=user.id,
                    preview_image_url=all_images[0] if all_images else None,
                    listings=top_listings,
                    report=result.model_dump(),
                )
            )
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            print(f"Failed to save report for user {user.username}: {exc}")

        return result

    finally:
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)


@app.get("/reports", response_model=list[ReportListItem])
async def list_reports(
    user: db.User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(db.get_session),
):
    """List the current user's saved reports, newest first."""
    rows = await session.scalars(
        select(db.Report)
        .where(db.Report.user_id == user.id)
        .order_by(db.Report.created_at.desc())
    )
    return [
        ReportListItem(
            id=r.id,
            created_at=r.created_at,
            preview_image_url=r.preview_image_url,
            summary=r.report.get("report", {}).get("summary", ""),
        )
        for r in rows
    ]


@app.get("/reports/{report_id}", response_model=StoredReport)
async def get_report(
    report_id: int,
    user: db.User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(db.get_session),
):
    """Fetch one saved report (must belong to the current user)."""
    report = await session.get(db.Report, report_id)
    if report is None or report.user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found.")
    return StoredReport(
        id=report.id,
        created_at=report.created_at,
        preview_image_url=report.preview_image_url,
        report=ProductIntelligenceReport(**report.report),
    )

import asyncio
import os
import shutil
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import statistics
from collections import Counter

import admin
import auth
import config
import db
import pipeline
import ratelimit
import storage
from models import (
    FoundSite,
    MergedReport,
    ReportGridItem,
    ReportStats,
    ReportStatus,
    SiteResult,
)

# Schema is managed by Alembic — run `alembic upgrade head` (see README).
app = FastAPI(title="Snapworth")

# Rate limiting (slowapi): register the limiter and the 429 handler.
app.state.limiter = ratelimit.limiter
app.add_exception_handler(RateLimitExceeded, ratelimit.rate_limit_handler)

# Auth routes (register/login/logout/me/invite check) and admin routes.
app.include_router(auth.router)
app.include_router(admin.router)

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

# Keep references to spawned background jobs so they aren't garbage-collected.
_jobs: set[asyncio.Task] = set()


@app.post("/upload-image")
@ratelimit.limiter.limit(config.UPLOAD_RATE_LIMIT, key_func=ratelimit.user_or_ip)
async def upload_image(
    request: Request,
    file: UploadFile = File(...),
    user: db.User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(db.get_session),
):
    """Start a sourcing job and return its id immediately.

    The pipeline runs in the background (pipeline.run) and writes progress to the
    DB; the client polls GET /reports/{id} to render each step as it completes.
    """
    # Persist the upload to a temp path the background job will read then delete.
    file_extension = os.path.splitext(file.filename or "")[1]
    temp_image_path = f"/tmp/{uuid.uuid4().hex}{file_extension}"
    with open(temp_image_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    report = db.Report(user_id=user.id, status="processing")
    session.add(report)
    await session.commit()
    await session.refresh(report)

    task = asyncio.create_task(pipeline.run(report.id, temp_image_path))
    _jobs.add(task)
    task.add_done_callback(_jobs.discard)

    return {"id": report.id, "status": report.status}


def _compute_stats(report: db.Report) -> ReportStats:
    sites = report.sites or []
    prices = [s["price_value"]
              for s in sites if s.get("price_value") is not None]
    ratings = [s["rating_value"]
               for s in sites if s.get("rating_value") is not None]
    currencies = [s["currency"] for s in sites if s.get("currency")]

    stats = ReportStats(
        sites_found=len(report.listings or []),
        sites_with_price=len(prices),
        currency=Counter(currencies).most_common(1)[
            0][0] if currencies else None,
        price_values=sorted(prices),
        avg_rating=round(statistics.fmean(ratings), 2) if ratings else None,
        total_reviews=sum(s["review_count"]
                          for s in sites if s.get("review_count")),
    )
    if prices:
        stats.price_min = min(prices)
        stats.price_max = max(prices)
        stats.price_median = round(statistics.median(prices), 2)
        if len(prices) >= 2:
            q1, _, q3 = statistics.quantiles(
                prices, n=4)  # returns 3 cut points
            stats.price_q1 = round(q1, 2)
            stats.price_q3 = round(q3, 2)
    return stats


def _to_status(report: db.Report) -> ReportStatus:
    return ReportStatus(
        id=report.id,
        status=report.status,
        image_url=report.image_url,
        error=report.error,
        created_at=report.created_at,
        started_at=report.started_at,
        finished_at=report.finished_at,
        found_sites=[FoundSite(**s) for s in (report.listings or [])],
        sites=[SiteResult(**s) for s in (report.sites or [])],
        report=MergedReport(**report.report) if report.report else None,
        stats=_compute_stats(report),
    )


@app.get("/reports", response_model=list[ReportGridItem])
async def list_reports(
    user: db.User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(db.get_session),
):
    """Grid of the current user's uploads, newest first."""
    rows = await session.scalars(
        select(db.Report)
        .where(db.Report.user_id == user.id)
        .order_by(db.Report.created_at.desc())
    )
    return [
        ReportGridItem(
            id=r.id,
            status=r.status,
            image_url=r.image_url,
            created_at=r.created_at,
            started_at=r.started_at,
            finished_at=r.finished_at,
            summary=(r.report or {}).get("summary") if r.report else None,
        )
        for r in rows
    ]


@app.get("/reports/{report_id}", response_model=ReportStatus)
async def get_report(
    report_id: int,
    user: db.User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(db.get_session),
):
    """Live status of one job (must belong to the current user)."""
    report = await session.get(db.Report, report_id)
    if report is None or report.user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found.")
    return _to_status(report)


@app.get("/reports/{report_id}/images/{site_index}/{filename}")
async def get_report_image(
    report_id: int,
    site_index: int,
    filename: str,
    user: db.User = Depends(auth.get_current_user),
    session: AsyncSession = Depends(db.get_session),
):
    """Serve a stored product image — only to the report's owner."""
    report = await session.get(db.Report, report_id)
    if report is None or report.user_id != user.id:
        raise HTTPException(status_code=404, detail="Not found.")
    path = storage.image_path(report_id, site_index, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Image not found.")
    return FileResponse(path)

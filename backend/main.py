import asyncio
import os
import shutil
import uuid

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import admin
import auth
import config
import db
import pipeline
import ratelimit
from models import FoundSite, MergedReport, ReportGridItem, ReportStatus, SiteResult

# Schema is managed by Alembic — run `alembic upgrade head` (see README).
app = FastAPI(title="Product Sourcing Intelligence Agent")

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

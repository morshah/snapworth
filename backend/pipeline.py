"""Background sourcing pipeline.

Runs after `POST /upload-image` returns, writing progress to the DB after every
step (image hosted → sites found → each site visited & summarized → merged
report). The frontend polls `GET /reports/{id}` and renders each step live.
Because all state is in the DB, leaving and returning to the page just re-reads
the current progress.
"""
import os
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm.attributes import flag_modified

import config
import services
import storage
from db import AsyncSessionLocal, Report


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso() -> str:
    return _utcnow().isoformat()


async def run(report_id: int, image_path: str) -> None:
    """Execute the full pipeline for one report, committing after each step."""
    try:
        async with AsyncSessionLocal() as session:
            report = await session.get(Report, report_id)
            if report is None:
                return

            report.status = "searching"
            report.started_at = _utcnow()
            await session.commit()

            # 1. Host the uploaded image, then reverse-image-search.
            image_url = await services.host_image(image_path)
            report.image_url = image_url
            report.preview_image_url = image_url
            await session.commit()

            found = await services.serpapi_lens(image_url)
            report.listings = found[: config.MAX_FOUND_SITES]
            await session.commit()

            # 2. Business rule: fewer than 3 matches → soft error.
            if len(found) < 3:
                report.status = "error"
                report.error = (
                    "Less than 3 product matches found. Please try again with a clearer photo."
                )
                report.finished_at = _utcnow()
                await session.commit()
                return

            # 3. Seed the visit list (top N) and move to scraping.
            to_visit = found[: config.MAX_LISTINGS]
            sites = [
                {
                    "index": i,
                    "title": s.get("title"),
                    "source": s.get("source"),
                    "link": s.get("link"),
                    "thumbnail": s.get("thumbnail"),
                    "price": s.get("price"),
                    "status": "pending",
                    "summary": None,
                    "description": None,
                    "manufacturer": None,
                    "seller": None,
                    "rating": None,
                    "barcodes": [],
                    "specs": {},
                    "images": [],
                    "started_at": None,
                    "finished_at": None,
                }
                for i, s in enumerate(to_visit)
            ]
            report.status = "scraping"
            report.sites = sites
            await session.commit()

            # 4. Visit each site: scrape → per-site AI summary. Commit after each
            #    so the poller sees them appear one by one. flag_modified is
            #    required because in-place JSON mutations aren't auto-tracked.
            for i, listing in enumerate(to_visit):
                sites[i]["status"] = "visiting"
                sites[i]["started_at"] = _iso()
                flag_modified(report, "sites")
                await session.commit()

                try:
                    scraped = await services.scrape_listing(listing["link"])
                    images = await _store_site_images(report_id, i, scraped.get("image_urls", []))
                    summary = await services.summarize_site(listing, scraped)
                    sites[i].update(
                        {
                            "description": scraped.get("description"),
                            "price": scraped.get("price") or sites[i]["price"],
                            "price_value": scraped.get("price_value"),
                            "currency": scraped.get("currency"),
                            "manufacturer": scraped.get("manufacturer"),
                            "seller": scraped.get("seller"),
                            "rating": scraped.get("rating"),
                            "rating_value": scraped.get("rating_value"),
                            "review_count": scraped.get("review_count"),
                            "reviews": scraped.get("reviews") or [],
                            "barcodes": scraped.get("barcodes") or [],
                            "specs": scraped.get("specs") or {},
                            "images": images,
                            "summary": summary,
                            "status": "done",
                        }
                    )
                except Exception as exc:  # noqa: BLE001 — one bad site shouldn't kill the run
                    sites[i]["status"] = "failed"
                    sites[i]["summary"] = f"Could not process this site ({exc})."
                sites[i]["finished_at"] = _iso()
                flag_modified(report, "sites")
                await session.commit()

            # 5. Merge everything into the final report.
            report.status = "summarizing"
            await session.commit()

            merged = await services.generate_ai_report(sites)
            report.report = merged.model_dump()
            report.status = "done"
            report.finished_at = _utcnow()
            await session.commit()

    except HTTPException as exc:
        await _fail(report_id, str(exc.detail))
    except Exception as exc:  # noqa: BLE001
        await _fail(report_id, str(exc))
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)


async def _store_site_images(report_id: int, site_index: int, urls: list) -> list:
    """Download up to MAX_IMAGES_PER_SITE images and save them under the
    product's folder. Returns served endpoint paths (owner-only access)."""
    served: list = []
    for url in urls[: config.MAX_IMAGES_PER_SITE]:
        got = await services.fetch_image(url)
        if not got:
            continue
        content, ctype = got
        filename = storage.save_image(report_id, site_index, len(served), content, ctype)
        served.append(f"/reports/{report_id}/images/{site_index}/{filename}")
    return served


async def _fail(report_id: int, message: str) -> None:
    async with AsyncSessionLocal() as session:
        report = await session.get(Report, report_id)
        if report is not None:
            report.status = "error"
            report.error = message
            report.finished_at = _utcnow()
            await session.commit()

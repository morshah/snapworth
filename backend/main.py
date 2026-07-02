import asyncio
import os
import shutil
import uuid

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import config
import services
from models import ProductIntelligenceReport

app = FastAPI(title="Product Sourcing Intelligence Agent")

# Allow the Next.js dev server (http://localhost:3000) to call this API from
# the browser. Without this, cross-origin fetches fail with "Failed to fetch".
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/upload-image", response_model=ProductIntelligenceReport)
async def upload_image(file: UploadFile = File(...)):
    """Upload an image → reverse image search → scrape listings → AI report.

    Requires SERPAPI_API_KEY, IMGBB_API_KEY, and ANTHROPIC_API_KEY (see
    backend/.env.example). Missing keys return a 503 naming the variable.
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

        # 7. Return the structured response.
        return ProductIntelligenceReport(
            report=ai_report,
            images=all_images,
            pdf_links=list(dict.fromkeys(all_pdf_links)),
            video_links=list(dict.fromkeys(all_video_links)),
        )

    finally:
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)

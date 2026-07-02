"""Real integrations for the product-sourcing pipeline.

External integrations used by the background pipeline:
  - host_image / serpapi_lens          →  imgbb hosting + SerpApi Google Lens
  - scrape_listing                     →  httpx + BeautifulSoup (best-effort)
  - summarize_site / generate_ai_report →  Anthropic Claude (per-site + merged)

Missing API keys raise HTTPException(503) with a message naming the env var,
so the app runs and tells the operator exactly what to configure.
"""
import base64
import json
from typing import Any, Dict, List

import httpx
from anthropic import AsyncAnthropic
from bs4 import BeautifulSoup
from fastapi import HTTPException

import config
from models import MergedReport

SERPAPI_URL = "https://serpapi.com/search.json"
IMGBB_URL = "https://api.imgbb.com/1/upload"


def _require(key: str | None, env_var: str) -> str:
    if not key:
        raise HTTPException(
            status_code=503,
            detail=f"{env_var} is not configured. Set it in backend/.env to enable this feature.",
        )
    return key


async def host_image(image_path: str) -> str:
    """Upload the local image to imgbb and return a public URL.

    SerpApi's Google Lens engine fetches the image by URL, so a locally saved
    file must be hosted somewhere publicly reachable first.
    """
    api_key = _require(config.IMGBB_API_KEY, "IMGBB_API_KEY")
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(IMGBB_URL, data={"key": api_key, "image": encoded})
    resp.raise_for_status()
    return resp.json()["data"]["url"]


async def serpapi_lens(public_url: str) -> List[Dict[str, Any]]:
    """Find product listings matching an already-hosted image via Google Lens.

    Returns a normalized list of listing dicts. Real image URLs (thumbnails)
    come straight from Google, so they render in the UI.
    """
    api_key = _require(config.SERPAPI_API_KEY, "SERPAPI_API_KEY")

    params = {
        "engine": "google_lens",
        "url": public_url,
        "api_key": api_key,
    }
    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.get(SERPAPI_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    if "error" in data:
        raise HTTPException(status_code=502, detail=f"Reverse image search failed: {data['error']}")

    listings: List[Dict[str, Any]] = []
    for match in data.get("visual_matches", []):
        price = match.get("price") or {}
        listings.append(
            {
                "title": match.get("title"),
                "source": match.get("source"),
                "link": match.get("link"),
                "price": price.get("value"),
                "thumbnail": match.get("thumbnail"),
            }
        )
    return listings


async def scrape_listing(url: str) -> Dict[str, Any]:
    """Best-effort scrape of a single product page.

    Many retailers block scrapers or render with JS; on any failure this
    returns an empty-ish dict so the pipeline degrades gracefully rather
    than failing the whole request.
    """
    result: Dict[str, Any] = {"source_url": url, "images": [], "pdf_links": [], "video_links": []}
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; ProductSourcingBot/1.0)"}
        async with httpx.AsyncClient(
            timeout=config.SCRAPE_TIMEOUT_SECONDS, follow_redirects=True, headers=headers
        ) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        def meta(prop: str) -> str | None:
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            return tag.get("content") if tag else None

        result["title"] = meta("og:title") or (soup.title.string if soup.title else None)
        result["description"] = meta("og:description") or meta("description")
        result["price"] = meta("og:price:amount") or meta("product:price:amount")

        og_image = meta("og:image")
        if og_image:
            result["images"].append(og_image)
        result["pdf_links"] = [
            a["href"] for a in soup.find_all("a", href=True) if a["href"].lower().endswith(".pdf")
        ][:3]
    except Exception as exc:  # noqa: BLE001 — scraping is inherently unreliable
        print(f"Scrape failed for {url}: {exc}")
    return result


async def _claude_text(system: str, user: str, max_tokens: int) -> str:
    api_key = _require(config.ANTHROPIC_API_KEY, "ANTHROPIC_API_KEY")
    client = AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user[:100_000]}],
    )
    return "".join(b.text for b in message.content if b.type == "text").strip()


def _parse_json(text: str) -> Any:
    if text.startswith("```"):  # strip an accidental ```json fence
        text = text.split("```", 2)[1].removeprefix("json").strip()
    return json.loads(text)


async def summarize_site(listing: Dict[str, Any], scraped: Dict[str, Any]) -> str:
    """Short, plain-language summary of a single visited listing."""
    data = json.dumps(
        {
            "title": listing.get("title"),
            "source": listing.get("source"),
            "price": listing.get("price"),
            "description": scraped.get("description"),
        },
        default=str,
    )
    system = (
        "You summarize a single online product listing in 1–2 concise sentences: what it is, "
        "the seller/source, price if known, and anything notable. Plain text only, no preamble. "
        "Base it only on the data provided."
    )
    return await _claude_text(system, data, max_tokens=200)


async def generate_ai_report(sites: List[Dict[str, Any]]) -> MergedReport:
    """Merge all visited-site data into one report using Claude."""
    payload = json.dumps({"sites": sites}, default=str)
    system = (
        "You are a product-sourcing intelligence analyst. You are given data for a single product "
        "gathered across multiple online retailers (per-site summaries, prices, descriptions). "
        "Synthesize ONE unbiased report merging information across all sites.\n"
        "Respond with ONLY a JSON object (no markdown, no code fences) with exactly these keys:\n"
        '  "summary": string — merged product description across all sites,\n'
        '  "features": array of strings — merged feature list,\n'
        '  "specifications": object of key/value pairs — merged specs,\n'
        '  "pricing_summary": string — pricing observed across sites,\n'
        '  "recommendation": string — overall sourcing recommendation.\n'
        "Base every claim on the provided data; do not invent details."
    )
    text = await _claude_text(system, payload, max_tokens=2000)
    try:
        return MergedReport(**_parse_json(text))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to parse AI report: {exc}")

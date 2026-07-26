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
import re
from typing import Any, Dict, List
from urllib.parse import urljoin

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


_UA = {"User-Agent": "Mozilla/5.0 (compatible; ProductSourcingBot/1.0)"}
_IMG_SKIP = ("logo", "sprite", "icon", "placeholder", "pixel", "spinner", "badge")


def _as_list(v: Any) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _name(v: Any) -> str | None:
    if isinstance(v, str):
        return v.strip() or None
    if isinstance(v, dict):
        return _name(v.get("name"))
    if isinstance(v, list) and v:
        return _name(v[0])
    return None


_PRICE_RE = re.compile(r"(\d[\d,]*\.?\d*)")
_CURRENCY_SYMBOLS = (("$", "USD"), ("£", "GBP"), ("€", "EUR"), ("¥", "JPY"))


def _parse_price(s: Any) -> tuple[float | None, str | None]:
    """Extract a numeric price and currency code from a messy price string."""
    if s is None:
        return None, None
    text = str(s)
    match = _PRICE_RE.search(text.replace(",", ""))
    value = float(match.group(1)) if match else None
    currency = next((code for sym, code in _CURRENCY_SYMBOLS if sym in text), None)
    if currency is None:
        code = re.search(r"\b([A-Z]{3})\b", text)
        currency = code.group(1) if code else None
    return value, currency


def _num(v: Any) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _extract_reviews(product: dict) -> list:
    reviews = []
    for r in _as_list(product.get("review")):
        if not isinstance(r, dict):
            continue
        rating = r.get("reviewRating")
        rating_val = rating.get("ratingValue") if isinstance(rating, dict) else None
        body = r.get("reviewBody") or r.get("description")
        if body:
            reviews.append({
                "author": _name(r.get("author")),
                "rating": str(rating_val) if rating_val is not None else None,
                "body": str(body)[:400],
            })
        if len(reviews) >= 5:
            break
    return reviews


def _jsonld_nodes(soup: BeautifulSoup) -> List[dict]:
    """All JSON-LD objects on the page (flattening lists and @graph)."""
    nodes: List[dict] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:  # noqa: BLE001
            continue
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list):
                stack.extend(cur)
            elif isinstance(cur, dict):
                stack.extend(_as_list(cur.get("@graph")))
                nodes.append(cur)
    return nodes


def _is_product(node: dict) -> bool:
    types = node.get("@type")
    types = types if isinstance(types, list) else [types]
    return any(isinstance(t, str) and t.lower() == "product" for t in types)


def _extract_jsonld_product(nodes: List[dict], result: dict, images: list, barcodes: list, sellers: list, specs: dict) -> None:
    product = next((n for n in nodes if _is_product(n)), None)
    if product is None:
        return

    result["title"] = result["title"] or _name(product.get("name"))
    if isinstance(product.get("description"), str):
        result["description"] = product["description"].strip()
    result["manufacturer"] = _name(product.get("manufacturer")) or _name(product.get("brand"))

    for img in _as_list(product.get("image")):
        if isinstance(img, str):
            images.append(img)
        elif isinstance(img, dict):
            u = img.get("url") or img.get("contentUrl")
            if u:
                images.append(u)

    for key in ("gtin13", "gtin12", "gtin8", "gtin14", "gtin", "ean", "upc", "isbn"):
        if product.get(key):
            barcodes.append(str(product[key]))
    for key, label in (("mpn", "MPN"), ("sku", "SKU"), ("model", "Model"), ("color", "Color")):
        if product.get(key):
            specs.setdefault(label, str(product[key]))

    offer_nodes: list = []
    for off in _as_list(product.get("offers")):
        if isinstance(off, dict):
            offer_nodes.extend(_as_list(off.get("offers")))
            offer_nodes.append(off)
    for off in offer_nodes:
        if not isinstance(off, dict):
            continue
        price = off.get("price") or off.get("lowPrice")
        if price and not result["price"]:
            result["price"] = f"{off.get('priceCurrency', '')} {price}".strip()
            result["price_value"], cur = _parse_price(price)
            result["currency"] = off.get("priceCurrency") or cur
        seller = _name(off.get("seller"))
        if seller:
            sellers.append(seller)

    rating = product.get("aggregateRating")
    if isinstance(rating, dict) and rating.get("ratingValue"):
        count = rating.get("reviewCount") or rating.get("ratingCount")
        result["rating"] = f"{rating['ratingValue']}" + (f" ({count} reviews)" if count else "")
        result["rating_value"] = _num(rating.get("ratingValue"))
        result["review_count"] = int(_num(count)) if _num(count) is not None else None

    result["reviews"] = _extract_reviews(product)

    for prop in _as_list(product.get("additionalProperty")):
        if isinstance(prop, dict) and prop.get("name") and prop.get("value") is not None:
            specs[str(prop["name"])] = str(prop["value"])


async def scrape_listing(url: str) -> Dict[str, Any]:
    """Best-effort rich scrape of a product page.

    Extracts from JSON-LD/schema.org (images, brand/manufacturer, GTIN/UPC
    barcodes, seller, price, rating, specs) with Open Graph / meta / <img>
    fallbacks. Many retailers block bots or render with JS; on any failure this
    returns an empty-ish dict so the pipeline degrades gracefully.
    """
    result: Dict[str, Any] = {
        "source_url": url,
        "title": None,
        "description": None,
        "price": None,
        "price_value": None,
        "currency": None,
        "manufacturer": None,
        "seller": None,
        "rating": None,
        "rating_value": None,
        "review_count": None,
        "reviews": [],
        "barcodes": [],
        "specs": {},
        "image_urls": [],
    }
    images: list = []
    barcodes: list = []
    sellers: list = []
    specs: dict = {}
    try:
        async with httpx.AsyncClient(
            timeout=config.SCRAPE_TIMEOUT_SECONDS, follow_redirects=True, headers=_UA
        ) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        def meta(prop: str) -> str | None:
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            return tag.get("content") if tag and tag.get("content") else None

        _extract_jsonld_product(_jsonld_nodes(soup), result, images, barcodes, sellers, specs)

        # Fallbacks from meta tags.
        result["title"] = result["title"] or meta("og:title") or (soup.title.string if soup.title else None)
        result["description"] = result["description"] or meta("og:description") or meta("description")
        result["price"] = result["price"] or meta("og:price:amount") or meta("product:price:amount")
        if result["price"] and result["price_value"] is None:
            result["price_value"], cur = _parse_price(result["price"])
            result["currency"] = result["currency"] or meta("og:price:currency") or meta("product:price:currency") or cur
        result["manufacturer"] = result["manufacturer"] or meta("product:brand") or meta("og:brand")

        # Images from all og:image / twitter:image / link rel=image_src / <img>.
        for tag in soup.find_all("meta", property="og:image"):
            if tag.get("content"):
                images.append(tag["content"])
        for tag in soup.find_all("meta", attrs={"name": "twitter:image"}):
            if tag.get("content"):
                images.append(tag["content"])
        link = soup.find("link", rel="image_src")
        if link and link.get("href"):
            images.append(link["href"])
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-old-hires")
            if src and any(src.lower().split("?")[0].endswith(e) for e in (".jpg", ".jpeg", ".png", ".webp")):
                images.append(src)

        # Normalize: absolutize, drop data URIs / likely non-product assets, dedupe.
        seen = set()
        for raw in images:
            if not raw or raw.startswith("data:"):
                continue
            absolute = urljoin(url, raw)
            low = absolute.lower()
            if any(bad in low for bad in _IMG_SKIP) or absolute in seen:
                continue
            seen.add(absolute)
            result["image_urls"].append(absolute)

        result["barcodes"] = list(dict.fromkeys(barcodes))
        result["seller"] = sellers[0] if sellers else None
        result["specs"] = specs
    except Exception as exc:  # noqa: BLE001 — scraping is inherently unreliable
        print(f"Scrape failed for {url}: {exc}")
    return result


async def fetch_image(url: str) -> tuple[bytes, str] | None:
    """Download one image; None on failure or if it isn't a real image."""
    try:
        async with httpx.AsyncClient(
            timeout=config.SCRAPE_TIMEOUT_SECONDS, follow_redirects=True, headers=_UA
        ) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if not ctype.startswith("image/") or len(resp.content) < 1500:  # skip icons/errors
            return None
        return resp.content, ctype
    except Exception:  # noqa: BLE001
        return None


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
            "title": scraped.get("title") or listing.get("title"),
            "source": listing.get("source"),
            "price": scraped.get("price") or listing.get("price"),
            "manufacturer": scraped.get("manufacturer"),
            "seller": scraped.get("seller"),
            "barcodes": scraped.get("barcodes"),
            "rating": scraped.get("rating"),
            "reviews": scraped.get("reviews"),
            "description": scraped.get("description"),
            "specs": scraped.get("specs"),
        },
        default=str,
    )
    system = (
        "You summarize a single online product listing in 2–3 concise sentences: what it is, "
        "the seller/source, price, manufacturer/brand, and anything notable (ratings, what "
        "customers say, key specs). Plain text only, no preamble. Base it only on the data provided."
    )
    return await _claude_text(system, data, max_tokens=300)


async def generate_ai_report(sites: List[Dict[str, Any]]) -> MergedReport:
    """Merge all visited-site data into one report using Claude."""
    payload = json.dumps({"sites": sites}, default=str)
    system = (
        "You are a product-sourcing analyst preparing a concise business case for a sourcing "
        "manager who will decide whether to APPROVE this product for purchase. You are given data "
        "for a single product gathered across multiple online retailers (per-site summaries, "
        "prices, manufacturers, sellers, barcodes, descriptions, specs, ratings, customer reviews).\n"
        "Write the case objectively — highlight genuine strengths AND risks so the manager can "
        "decide. Respond with ONLY a JSON object (no markdown, no code fences) with exactly these keys:\n"
        '  "summary": string — the case: what the product is and why it is (or isn\'t) worth sourcing,\n'
        '  "features": array of strings — key product features,\n'
        '  "specifications": object of key/value pairs — merged specs,\n'
        '  "pricing_summary": string — pricing across sites and margin/sourcing implications,\n'
        '  "recommendation": string — a clear verdict for the manager,\n'
        '  "pros": array of strings — reasons to approve,\n'
        '  "cons": array of strings — risks/reasons for caution,\n'
        '  "customer_sentiment": string — what customers say (from ratings/reviews); empty string if none,\n'
        '  "manufacturer": string — best manufacturer/brand found (empty string if none),\n'
        '  "barcodes": array of strings — any GTIN/UPC/EAN barcodes found,\n'
        '  "wholesalers": array of strings — sellers/wholesalers found.\n'
        "Base every claim on the provided data; do not invent details."
    )
    text = await _claude_text(system, payload, max_tokens=config.REPORT_MAX_TOKENS)
    try:
        return MergedReport(**_parse_json(text))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "The AI report came back incomplete (likely truncated). "
                f"Try again. ({exc})"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Failed to parse AI report: {exc}")

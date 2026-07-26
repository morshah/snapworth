"""Local image storage, organized per product (report).

Layout:  {STORAGE_DIR}/reports/{report_id}/site_{site_index}/img_{n}.{ext}

Images are NOT public — they're written here and served only through the
ownership-checked endpoint in main.py. This module is deliberately small and
side-effect-only so it can be swapped for S3/R2 later without touching callers.
"""
import os

import config

_EXT_BY_TYPE = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/avif": "avif",
}


def _site_dir(report_id: int, site_index: int) -> str:
    return os.path.join(config.STORAGE_DIR, "reports", str(report_id), f"site_{site_index}")


def save_image(report_id: int, site_index: int, n: int, content: bytes, content_type: str) -> str:
    """Write one image and return its filename (not the full path)."""
    ext = _EXT_BY_TYPE.get((content_type or "").split(";")[0].strip().lower(), "jpg")
    directory = _site_dir(report_id, site_index)
    os.makedirs(directory, exist_ok=True)
    filename = f"img_{n}.{ext}"
    with open(os.path.join(directory, filename), "wb") as f:
        f.write(content)
    return filename


def image_path(report_id: int, site_index: int, filename: str) -> str | None:
    """Resolve a stored image to an absolute path, or None if it escapes the
    storage root / doesn't exist (path-traversal safe)."""
    if "/" in filename or "\\" in filename or filename in ("", ".", ".."):
        return None
    base = os.path.realpath(_site_dir(report_id, site_index))
    path = os.path.realpath(os.path.join(base, filename))
    if os.path.commonpath([base, path]) != base or not os.path.isfile(path):
        return None
    return path

"""Pydantic models shared across the API and the service layer.

The frontend renders directly against these field names — changing a field
here is a breaking change to frontend/components/ImageUploadForm.js.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AIReport(BaseModel):
    summary: str
    features_list: List[str]
    specs: Dict[str, Any]
    pricing_summary: str
    recommendation_sentiment: str


class ProductIntelligenceReport(BaseModel):
    report: AIReport
    images: List[str]
    pdf_links: List[str]
    video_links: List[str]


class UserCredentials(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    """Non-sensitive user info returned to the client (no token — it's a cookie)."""
    username: str


class ReportListItem(BaseModel):
    """One row in a user's saved-report history."""
    id: int
    created_at: datetime
    preview_image_url: Optional[str] = None
    summary: str


class StoredReport(BaseModel):
    """A full saved report retrieved from history."""
    id: int
    created_at: datetime
    preview_image_url: Optional[str] = None
    report: ProductIntelligenceReport

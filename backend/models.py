"""Pydantic models shared across the API and the service layer.

The frontend renders directly against these field names — changing a field
here is a breaking change to frontend/components/ImageUploadForm.js.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Review(BaseModel):
    author: Optional[str] = None
    rating: Optional[str] = None
    body: Optional[str] = None


class MergedReport(BaseModel):
    """The final product report — a decision case for a sourcing manager."""
    summary: str
    features: List[str]
    specifications: Dict[str, Any]
    pricing_summary: str
    recommendation: str
    pros: List[str] = []
    cons: List[str] = []
    customer_sentiment: Optional[str] = None
    manufacturer: Optional[str] = None
    barcodes: List[str] = []
    wholesalers: List[str] = []


class FoundSite(BaseModel):
    """One site returned by the reverse image search (before visiting)."""
    title: Optional[str] = None
    source: Optional[str] = None
    link: Optional[str] = None
    thumbnail: Optional[str] = None
    price: Optional[str] = None


class SiteResult(BaseModel):
    """A visited site, with what was found + a per-site AI summary."""
    index: int
    title: Optional[str] = None
    source: Optional[str] = None
    link: Optional[str] = None
    thumbnail: Optional[str] = None
    status: str = "pending"  # pending | visiting | done | failed
    summary: Optional[str] = None
    price: Optional[str] = None
    price_value: Optional[float] = None
    currency: Optional[str] = None
    description: Optional[str] = None
    manufacturer: Optional[str] = None
    seller: Optional[str] = None
    rating: Optional[str] = None
    rating_value: Optional[float] = None
    review_count: Optional[int] = None
    reviews: List[Review] = []
    barcodes: List[str] = []
    specs: Dict[str, Any] = {}
    images: List[str] = []             # served image endpoint paths
    started_at: Optional[str] = None   # ISO strings (stored inside JSON)
    finished_at: Optional[str] = None


class ReportStats(BaseModel):
    """Aggregate decision signals computed from the visited sites."""
    sites_found: int = 0
    sites_with_price: int = 0
    currency: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    price_median: Optional[float] = None
    price_q1: Optional[float] = None
    price_q3: Optional[float] = None
    price_values: List[float] = []
    avg_rating: Optional[float] = None
    total_reviews: int = 0


class ReportStatus(BaseModel):
    """Full live state of a sourcing job — the polling payload."""
    id: int
    status: str
    image_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    found_sites: List[FoundSite] = []
    sites: List[SiteResult] = []
    report: Optional[MergedReport] = None
    stats: ReportStats = ReportStats()


class ReportGridItem(BaseModel):
    """One card in the products grid."""
    id: int
    status: str
    image_url: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    summary: Optional[str] = None


class UserCredentials(BaseModel):
    username: str
    password: str


class InviteRegister(BaseModel):
    """Registration payload — requires a valid invite token (invite-only)."""
    username: str
    password: str
    token: str


class UserOut(BaseModel):
    """Non-sensitive user info returned to the client (no token — it's a cookie)."""
    username: str
    is_admin: bool = False


# --- Admin: user management ---

class UserAdminOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: datetime


class UserUpdate(BaseModel):
    is_admin: Optional[bool] = None
    password: Optional[str] = None  # optional password reset


# --- Admin: invitations ---

class InvitationCreate(BaseModel):
    email: Optional[str] = None
    grants_admin: bool = False


class InvitationOut(BaseModel):
    id: int
    token: str
    email: Optional[str] = None
    grants_admin: bool
    created_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime] = None


class InviteInfo(BaseModel):
    """Public-facing invite validity check for the accept page."""
    valid: bool
    email: Optional[str] = None

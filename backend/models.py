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

"""Pydantic models shared across the API and the service layer.

The frontend renders directly against these field names — changing a field
here is a breaking change to frontend/components/ImageUploadForm.js.
"""
from pydantic import BaseModel
from typing import List, Dict, Any


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


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

"""Pydantic schemas for the storage (Cloudinary) module."""

from pydantic import BaseModel


class CloudinarySignatureResponse(BaseModel):
    """Returned to frontend so it can upload directly to Cloudinary."""

    signature: str
    timestamp: int
    cloud_name: str
    api_key: str
    upload_preset: str
    folder: str


class CloudinaryWebhookPayload(BaseModel):
    """Cloudinary upload notification webhook payload (simplified)."""

    notification_type: str
    public_id: str
    secure_url: str
    resource_type: str
    format: str

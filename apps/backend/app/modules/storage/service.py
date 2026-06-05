"""Storage service — Cloudinary signed upload and resume text extraction."""

import hashlib
import hmac
import time

import cloudinary
import cloudinary.uploader
import fitz  # PyMuPDF

from app.config import settings

# Configure Cloudinary SDK on import
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)

RESUME_FOLDER = "eigensu/resumes"


def generate_upload_signature() -> dict:
    """Generate a signed upload payload for direct browser → Cloudinary uploads.

    The frontend uses this signature to upload files directly to Cloudinary
    without routing the file bytes through the FastAPI server.

    Returns:
        Dict with signature, timestamp, cloud_name, api_key, upload_preset, folder.
    """
    timestamp = int(time.time())
    params_to_sign = (
        f"folder={RESUME_FOLDER}"
        f"&timestamp={timestamp}"
        f"&upload_preset={settings.CLOUDINARY_UPLOAD_PRESET}"
    )

    signature = hmac.new(
        settings.CLOUDINARY_API_SECRET.encode(),
        params_to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()

    return {
        "signature": signature,
        "timestamp": timestamp,
        "cloud_name": settings.CLOUDINARY_CLOUD_NAME,
        "api_key": settings.CLOUDINARY_API_KEY,
        "upload_preset": settings.CLOUDINARY_UPLOAD_PRESET,
        "folder": RESUME_FOLDER,
    }


def verify_cloudinary_webhook(payload: bytes, signature_header: str) -> bool:
    """Verify Cloudinary's webhook notification signature.

    Cloudinary sends a X-Cld-Signature header. We verify it by computing
    the HMAC ourselves against the raw payload.
    """
    expected = hmac.new(
        settings.CLOUDINARY_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Phase 1 stub — extract raw text from a PDF using PyMuPDF.

    Phase 2 will pipe this text to an LLM endpoint (OpenAI / Gemini)
    to extract a structured list of skills as JSON.

    Args:
        file_bytes: Raw PDF bytes downloaded from Cloudinary.

    Returns:
        Concatenated plain text from all PDF pages.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)

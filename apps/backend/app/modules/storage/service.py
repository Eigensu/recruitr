"""Storage service — Cloudinary signed upload and resume text extraction."""

import hashlib
import hmac
import io
import re
import time
import uuid

import cloudinary
import cloudinary.uploader
import cloudinary.utils
import pymupdf  # the `fitz` import name is deprecated and warns on every import

from app.core.config import settings

# Configure Cloudinary SDK on import
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)

RESUME_FOLDER = "eigensu/resumes"
OFFER_LETTER_FOLDER = "eigensu/offers"


def generate_upload_signature() -> dict:
    """Generate a signed upload payload for direct browser → Cloudinary uploads.

    The frontend uses this signature to upload files directly to Cloudinary
    without routing the file bytes through the FastAPI server.

    Returns:
        Dict with signature, timestamp, cloud_name, api_key, upload_preset, folder.
    """
    timestamp = int(time.time())
    params_to_sign = {
        "folder": RESUME_FOLDER,
        "timestamp": timestamp,
        "upload_preset": settings.CLOUDINARY_UPLOAD_PRESET,
    }

    # Cloudinary signatures are a plain hash (SHA-1 by default) of the sorted
    # params concatenated with the API secret — NOT an HMAC. Reuse the SDK's
    # own signer so this stays correct if Cloudinary's algorithm/version changes.
    signature = cloudinary.utils.api_sign_request(params_to_sign, settings.CLOUDINARY_API_SECRET)

    return {
        "signature": signature,
        "timestamp": timestamp,
        "cloud_name": settings.CLOUDINARY_CLOUD_NAME,
        "api_key": settings.CLOUDINARY_API_KEY,
        "upload_preset": settings.CLOUDINARY_UPLOAD_PRESET,
        "folder": RESUME_FOLDER,
    }


def _unique_public_id(filename: str) -> str:
    """Build a collision-proof Cloudinary public_id that keeps the extension.

    Two bugs lived in the old `public_id=<filename stem>`:

    1. It was deterministic, and the upload passes `overwrite=False`. When a
       public_id already exists Cloudinary does not upload — it returns the
       EXISTING asset. Two candidates whose offer letters were both named
       "Offer Letter.pdf" (the common case — it is what most HR systems emit)
       meant the second upload silently reported success while handing back the
       first candidate's document, and re-uploading a corrected letter for one
       candidate did nothing at all.
    2. It stripped the extension. `resource_type="raw"` serves the public_id
       verbatim, so the delivered URL ended without ".pdf" and browsers would
       not open it as a PDF.

    A random suffix fixes (1); keeping the extension fixes (2). The original
    name is preserved (sanitised) so assets stay recognisable in the Cloudinary
    console.
    """
    base, dot, ext = filename.rpartition(".")
    if not dot:
        base, ext = filename, ""
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", base).strip("-") or "upload"
    public_id = f"{safe}-{uuid.uuid4().hex[:8]}"
    return f"{public_id}.{ext.lower()}" if ext else public_id


def upload_bytes_to_cloudinary(
    pdf_bytes: bytes, filename: str, folder: str = RESUME_FOLDER
) -> dict:
    """Upload raw file bytes directly to Cloudinary from the backend.

    Used by bulk-upload and the offer-letter flow — does NOT use the signed
    browser-upload flow (that one is staff-only; see storage/router.py). The
    file bytes are sent straight from the API server to Cloudinary, so no
    upload credential is ever handed to the caller.

    Returns:
        The Cloudinary upload result dict (includes public_id, secure_url).
    """
    return cloudinary.uploader.upload(
        pdf_bytes,
        resource_type="raw",
        folder=folder,
        public_id=_unique_public_id(filename),
        overwrite=False,
    )


def upload_offer_letter(file_bytes: bytes, filename: str) -> dict:
    """Upload an offer letter for a pipeline mapping.

    Thin wrapper over upload_bytes_to_cloudinary, in its own folder so offer
    letters don't mix with the resume pool.
    """
    return upload_bytes_to_cloudinary(file_bytes, filename, folder=OFFER_LETTER_FOLDER)


def delete_cloudinary_asset(public_id: str) -> None:
    """Delete a Cloudinary asset by its public_id."""
    cloudinary.uploader.destroy(public_id)


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
    """Extract raw text from a PDF file using PyMuPDF.

    Raises:
        ValueError: If file_bytes is not a PDF.
    """
    if not file_bytes.startswith(b"%PDF-"):
        raise ValueError("Input is not a PDF file")
    try:
        with pymupdf.open(stream=file_bytes, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    except ValueError:
        raise
    except Exception as exc:
        # PyMuPDF raises its own FileDataError for truncated, corrupt or
        # password-protected files. Callers (and this module's contract) expect
        # ValueError for anything wrong with the file, so a bad upload is a 400
        # rather than a 500 — matching how the DOCX branch already behaves.
        raise ValueError(f"Could not parse PDF file: {exc}") from exc


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract raw text from a .docx file using python-docx.

    Raises:
        ValueError: If file_bytes cannot be opened as a DOCX.
    """
    try:
        from docx import Document  # python-docx  # noqa: PLC0415

        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as exc:
        raise ValueError(f"Could not parse DOCX file: {exc}") from exc


def extract_text_from_file(file_bytes: bytes) -> str:
    """Detect file type from magic bytes and extract text.

    Supports PDF and DOCX. Old binary .doc is accepted for upload but
    cannot be parsed — callers should handle ValueError gracefully.

    Raises:
        ValueError: If the file format is unsupported or extraction fails.
    """
    if file_bytes.startswith(b"%PDF-"):
        return extract_text_from_pdf(file_bytes)
    # DOCX (and all OOXML formats) are ZIP archives starting with PK
    if file_bytes[:2] == b"PK":
        return extract_text_from_docx(file_bytes)
    raise ValueError("Unsupported file format. Only PDF and DOCX (Word) files can be parsed.")

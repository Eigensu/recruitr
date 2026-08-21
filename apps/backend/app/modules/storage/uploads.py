"""Reading an offer letter that arrives as a multipart upload.

Offer letters come to the API as file bytes rather than as a URL to confirm.
That is not an oversight: GET /api/v1/storage/sign is the only source of a
Cloudinary upload credential and it is deny_clients ("a credential to write
into the agency's Cloudinary account, which a client account has no reason to
hold"), so the signed browser-upload flow staff use for resumes is unreachable
from the client and referee portals — the only two places offer letters are
uploaded from. Taking a URL instead would also let a caller point a mapping's
offer letter at any address they liked.

Shared by both portals so they cannot drift on what they accept.
"""

from fastapi import HTTPException, UploadFile, status

MAX_OFFER_LETTER_BYTES = 10 * 1024 * 1024


async def read_offer_letter(file: UploadFile) -> tuple[bytes, str]:
    """Return (bytes, filename) for a valid offer letter, or raise 400/413."""
    filename = file.filename or "offer-letter.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PDF offer letters are accepted")

    file_bytes = await file.read()
    # UploadFile.size is not populated by every ASGI server, so the length of
    # what was actually read is the check that always runs.
    if len(file_bytes) > MAX_OFFER_LETTER_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Offer letter too large (max 10MB)"
        )

    return file_bytes, filename

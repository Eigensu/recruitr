"""Storage API router — Cloudinary signed upload and webhook."""

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status

from app.dependencies import get_current_user
from app.modules.auth.schemas import TokenPayload
from app.modules.storage import service
from app.modules.storage.schemas import CloudinarySignatureResponse

router = APIRouter()


@router.get("/sign", response_model=CloudinarySignatureResponse)
async def get_upload_signature(
    _: TokenPayload = Depends(get_current_user),  # noqa: B008
) -> CloudinarySignatureResponse:
    """Generate a signed payload so the frontend can upload directly to Cloudinary.

    The file bytes never touch the FastAPI server — only the signature is generated here.
    """
    sig_data = service.generate_upload_signature()
    return CloudinarySignatureResponse(**sig_data)


@router.post("/webhook/cloudinary")
async def handle_cloudinary_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_cld_signature: str = Header(..., alias="X-Cld-Signature"),
) -> dict:
    """Receive Cloudinary upload notifications.

    Cloudinary sends this after a resume is successfully uploaded.
    We verify the signature and kick off async text extraction.

    Security: Verified via HMAC-SHA256 against CLOUDINARY_WEBHOOK_SECRET.
    """
    payload = await request.body()

    if not service.verify_cloudinary_webhook(payload, x_cld_signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )

    # Phase 1 stub: just log the upload
    # Phase 2: background_tasks.add_task(extract_skills_with_llm, public_id, secure_url)
    return {"status": "received"}

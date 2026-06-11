"""Candidates API router."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.dependencies import get_current_user
from app.modules.auth.schemas import TokenPayload
from app.modules.candidates import service
from app.modules.candidates.schemas import (
    BulkUploadResult,
    CandidateCreate,
    CandidateListFilters,
    CandidateResponse,
    CandidateUpdate,
    CandidateUploadConfirm,
)

router = APIRouter()


@router.get("/tags", response_model=list[str])
async def list_tags(
    _: TokenPayload = Depends(get_current_user),
) -> list[str]:
    """Return all distinct candidate tags (global, not brand-scoped)."""
    return await service.get_distinct_tags()


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(
    search: str | None = Query(None, description="Search by name, email, skill, or tag"),
    source: Annotated[Literal["internal", "external"] | None, Query()] = None,
    tags: list[str] | None = Query(None),
    has_resume: bool | None = Query(None),
    has_cv_link: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _: TokenPayload = Depends(get_current_user),
) -> list[CandidateResponse]:
    filters = CandidateListFilters(
        search=search,
        source=source,
        tags=tags,
        has_resume=has_resume,
        has_cv_link=has_cv_link,
        page=page,
        limit=limit,
    )
    candidates = await service.list_candidates(filters)
    return [CandidateResponse(id=str(c.id), **c.model_dump(exclude={"id"})) for c in candidates]


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    data: CandidateCreate,
    _: TokenPayload = Depends(get_current_user),  # noqa: B008
) -> CandidateResponse:
    candidate = await service.create_candidate(data)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))


@router.post("/bulk-upload", response_model=BulkUploadResult)
async def bulk_upload(
    files: Annotated[list[UploadFile], File(description="PDF files to upload")],
    _: TokenPayload = Depends(get_current_user),
) -> BulkUploadResult:
    """Upload multiple PDF resumes. Upserts on matched email."""
    if len(files) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 files per request",
        )
    return await service.bulk_upload_candidates(files)


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: str,
    _: TokenPayload = Depends(get_current_user),  # noqa: B008
) -> CandidateResponse:
    candidate = await service.get_candidate(candidate_id)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))


@router.patch("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: str,
    data: CandidateUpdate,
    _: TokenPayload = Depends(get_current_user),
) -> CandidateResponse:
    candidate = await service.update_candidate(candidate_id, data)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))


@router.patch("/{candidate_id}/resume", response_model=CandidateResponse)
async def confirm_resume(
    candidate_id: str,
    data: CandidateUploadConfirm,
    _: TokenPayload = Depends(get_current_user),  # noqa: B008
) -> CandidateResponse:
    """Called after the frontend successfully uploads a resume to Cloudinary."""
    data.candidate_id = candidate_id
    candidate = await service.confirm_resume_upload(data)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))

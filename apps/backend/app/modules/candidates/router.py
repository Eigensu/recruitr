"""Candidates API router."""

from fastapi import APIRouter, Depends, Query

from app.modules.auth.schemas import TokenPayload
from app.modules.candidates import service
from app.modules.candidates.schemas import (
    CandidateCreate,
    CandidateResponse,
    CandidateUploadConfirm,
)
from app.dependencies import get_current_user

router = APIRouter()


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(
    search: str | None = Query(None, description="Search by name, email, or skill"),
    _: TokenPayload = Depends(get_current_user),
) -> list[CandidateResponse]:
    candidates = await service.list_candidates(search)
    return [CandidateResponse(id=str(c.id), **c.model_dump(exclude={"id"})) for c in candidates]


@router.post("", response_model=CandidateResponse, status_code=201)
async def create_candidate(
    data: CandidateCreate,
    _: TokenPayload = Depends(get_current_user),
) -> CandidateResponse:
    candidate = await service.create_candidate(data)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: str,
    _: TokenPayload = Depends(get_current_user),
) -> CandidateResponse:
    candidate = await service.get_candidate(candidate_id)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))


@router.patch("/{candidate_id}/resume", response_model=CandidateResponse)
async def confirm_resume(
    candidate_id: str,
    data: CandidateUploadConfirm,
    _: TokenPayload = Depends(get_current_user),
) -> CandidateResponse:
    """Called after the frontend successfully uploads a resume to Cloudinary."""
    data.candidate_id = candidate_id
    candidate = await service.confirm_resume_upload(data)
    return CandidateResponse(id=str(candidate.id), **candidate.model_dump(exclude={"id"}))

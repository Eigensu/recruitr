"""Pipeline (matching) API router."""

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.modules.auth.schemas import TokenPayload
from app.modules.candidates.schemas import CandidateMatchScore
from app.modules.pipeline import service
from app.modules.pipeline.schemas import MatchRequest, MatchResponse

router = APIRouter()


@router.get("/top-candidates", response_model=list[CandidateMatchScore])
async def get_top_candidates(
    position_id: str = Query(...),
    limit: int = Query(10, ge=1, le=50),
    _: TokenPayload = Depends(get_current_user),  # noqa: B008
) -> list[CandidateMatchScore]:
    """Return the top N candidates ranked by keyword match score for a position."""
    results = await service.find_top_candidates(position_id, limit)
    return [CandidateMatchScore(**r) for r in results]


@router.patch("/match", response_model=MatchResponse)
async def match_candidate(
    data: MatchRequest,
    current_user: TokenPayload = Depends(get_current_user),  # noqa: B008
) -> MatchResponse:
    """Atomically move a candidate onto a position and credit recruiter score."""
    recruiter = await service.match_candidate_to_position(
        position_id=data.position_id,
        candidate_id=data.candidate_id,
        recruiter_id=current_user.sub,
        target_status=data.target_status,
    )
    return MatchResponse(
        position_id=data.position_id,
        candidate_id=data.candidate_id,
        status=data.target_status,
        recruiter_daily_score=recruiter.daily_score,
    )

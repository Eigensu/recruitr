"""Pipeline (matching) API router."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.modules.auth.schemas import TokenPayload
from app.modules.candidates.schemas import CandidateMatchScore
from app.modules.pipeline import service
from app.modules.pipeline.schemas import FilteredCandidate, MatchRequest, MatchResponse

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


@router.get("/filtered", response_model=list[FilteredCandidate])
async def get_filtered_pipeline(
    position_id: str = Query(...),
    recruiter_id: str | None = Query(None),
    client_id: str | None = Query(None),
    source: str | None = Query(None),
    tags: list[str] | None = Query(None),
    stage: str | None = Query(None),
    mapped_after: datetime | None = Query(None),
    mapped_before: datetime | None = Query(None),
    _: TokenPayload = Depends(get_current_user),
) -> list[FilteredCandidate]:
    """Return the Kanban board for a position, scoped to its linked JobOpening.

    Both the unfiltered board (no filters) and every filtered view use this one
    endpoint, so they operate on the same underlying dataset. Filters: recruiter,
    client (opening override), stage, source, tags, mapped-date range.
    """
    results = await service.find_filtered_candidates(
        position_id=position_id,
        recruiter_id=recruiter_id,
        client_id=client_id,
        source=source,
        tags=tags,
        stage=stage,
        mapped_after=mapped_after,
        mapped_before=mapped_before,
    )
    return results


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

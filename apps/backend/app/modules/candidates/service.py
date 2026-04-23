"""Business logic for Candidate management."""

from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.modules.candidates.models import Candidate
from app.modules.candidates.schemas import CandidateCreate, CandidateUploadConfirm


async def create_candidate(data: CandidateCreate) -> Candidate:
    existing = await Candidate.find_one(Candidate.email == data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A candidate with this email already exists",
        )
    candidate = Candidate(**data.model_dump())
    await candidate.insert()
    return candidate


async def confirm_resume_upload(data: CandidateUploadConfirm) -> Candidate:
    """Attach Cloudinary public_id and URL to a candidate after upload."""
    candidate = await get_candidate(data.candidate_id)
    await candidate.set({
        "resume_public_id": data.resume_public_id,
        "resume_url": data.resume_url,
    })
    return candidate


async def get_candidate(candidate_id: str) -> Candidate:
    candidate = await Candidate.get(PydanticObjectId(candidate_id))
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate


async def list_candidates(search: str | None = None) -> list[Candidate]:
    if search:
        return await Candidate.find(
            {"$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"extracted_skills": {"$in": [search.lower()]}},
            ]}
        ).to_list()
    return await Candidate.find_all().to_list()

"""Core pipeline business logic: keyword matching and transactional candidate move."""

from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.database import get_client
from app.modules.candidates.models import Candidate
from app.modules.gamification.models import RecruiterProfile
from app.modules.positions.models import Position


async def find_top_candidates(position_id: str, limit: int = 10) -> list[dict]:
    """Run a MongoDB aggregation to score and rank candidates by keyword overlap.

    The score is computed entirely at the database layer using $setIntersection,
    ensuring performance at scale without loading all candidates into Python memory.
    """
    position = await Position.get(PydanticObjectId(position_id))
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")

    job_keywords = [kw.lower() for kw in position.requirements]

    pipeline = [
        {
            "$addFields": {
                "normalized_skills": {
                    "$map": {
                        "input": "$extracted_skills",
                        "as": "s",
                        "in": {"$toLower": "$$s"},
                    }
                }
            }
        },
        {
            "$addFields": {
                "match_score": {
                    "$cond": {
                        "if": {"$gt": [len(job_keywords), 0]},
                        "then": {
                            "$divide": [
                                {
                                    "$size": {
                                        "$setIntersection": [
                                            "$normalized_skills",
                                            job_keywords,
                                        ]
                                    }
                                },
                                len(job_keywords),
                            ]
                        },
                        "else": 0,
                    }
                }
            }
        },
        {"$match": {"match_score": {"$gt": 0}}},
        {"$sort": {"match_score": -1}},
        {"$limit": limit},
        {
            "$project": {
                "id": {"$toString": "$_id"},
                "name": 1,
                "email": 1,
                "resume_url": 1,
                "extracted_skills": 1,
                "match_score": 1,
            }
        },
    ]

    return await Candidate.aggregate(pipeline).to_list()


async def match_candidate_to_position(
    position_id: str,
    candidate_id: str,
    recruiter_id: str,
    target_status: str = "pending",
    points: int = 10,
) -> RecruiterProfile:
    """Atomically move a candidate onto a position and credit the recruiter's score.

    Wraps both MongoDB writes in a replica-set transaction so that a crash
    between the two updates cannot leave the data in a corrupted half-state.
    """
    pos_oid = PydanticObjectId(position_id)
    cand_oid = PydanticObjectId(candidate_id)

    client = get_client()

    async with await client.start_session() as session:  # noqa: SIM117
        async with session.start_transaction():
            # Verify both documents exist inside the transaction to avoid TOCTOU
            position = await Position.get(pos_oid, session=session)
            if not position:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Position not found",
                )
            if not await Candidate.get(cand_oid, session=session):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Candidate not found",
                )

            # 1. Push candidate into position's matched list
            await Position.find_one(Position.id == pos_oid, session=session).update(
                {
                    "$push": {
                        "matched_candidates": {
                            "candidate_id": cand_oid,
                            "status": target_status,
                            "feedback": None,
                        }
                    }
                },
                session=session,
            )

            # 2. Credit recruiter score (upsert in case profile doesn't exist yet)
            profile = await RecruiterProfile.find_one(
                RecruiterProfile.user_id == recruiter_id,
                RecruiterProfile.brand_id == position.brand_id,
                session=session,
            )
            if profile:
                await profile.inc(
                    {"daily_score": points, "weekly_score": points},
                    session=session,
                )
            else:
                profile = RecruiterProfile(
                    user_id=recruiter_id,
                    brand_id=position.brand_id,  # fallback brand
                    daily_score=points,
                    weekly_score=points,
                )
                await profile.insert(session=session)

    return profile

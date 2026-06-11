"""Core pipeline business logic: keyword matching and transactional candidate move."""

from datetime import UTC, datetime

from beanie import PydanticObjectId
from fastapi import HTTPException, status

from app.common.utils.object_id import to_object_id
from app.database import get_client
from app.modules.auth.models import User
from app.modules.brands.models import Brand
from app.modules.candidates.models import Candidate
from app.modules.dashboard.enums import PipelineStage
from app.modules.dashboard.models import CandidateMapping, DashboardEmployee, JobOpening
from app.modules.gamification.models import RecruiterProfile
from app.modules.positions.models import Position

# Drag target (3 Kanban columns) → representative CandidateMapping.pipeline_stage.
# Must round-trip with the stage→status bucketing in find_filtered_candidates.
_STATUS_TO_STAGE = {
    "pending": PipelineStage.shortlisted,
    "accepted": PipelineStage.offer_accepted,
    "rejected": PipelineStage.rejected,
}



async def resolve_employee_id(user_id: str, *, session=None) -> PydanticObjectId | None:
    """Resolve an authenticated User to a DashboardEmployee id (by email).

    Creates the employee on first use so recruiter activity is tracked consistently.
    """
    user = await User.get(PydanticObjectId(user_id))
    if not user:
        return None
    employee = await DashboardEmployee.find_one(
        DashboardEmployee.email == user.email, session=session
    )
    if employee:
        return employee.id
    employee = DashboardEmployee(name=user.full_name or user.email, email=user.email)
    await employee.insert(session=session)
    return employee.id


async def ensure_position_opening(position: Position) -> PydanticObjectId | None:
    """Ensure a Position is linked to a JobOpening, creating one if needed."""
    if position.job_opening_id:
        return position.job_opening_id

    client_name = "Unassigned Client"
    if position.brand_id:
        brand = await Brand.get(position.brand_id)
        if brand:
            client_name = brand.name

    opening = JobOpening(client_name=client_name, role=position.title)
    await opening.insert()
    position.job_opening_id = opening.id
    await position.save()
    return opening.id



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
                # Legacy-tolerant: fall back to dashboard-shaped field names.
                "name": {"$ifNull": ["$name", {"$ifNull": ["$full_name", "Unnamed"]}]},
                "email": 1,
                "resume_url": {"$ifNull": ["$resume_url", "$resume_link"]},
                "extracted_skills": {
                    "$ifNull": ["$extracted_skills", {"$ifNull": ["$skills", []]}]
                },
                "tags": {"$ifNull": ["$tags", []]},
                "source": {"$ifNull": ["$source", "internal"]},
                "cv_link": "$cv_link",
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

    # Verify both documents exist before opening a transaction
    position = await Position.get(pos_oid)
    if not position:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    if not await Candidate.get(cand_oid):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

    # Ensure the position is linked to a JobOpening before the transaction.
    opening_id = await ensure_position_opening(position)
    target_stage = _STATUS_TO_STAGE.get(target_status, PipelineStage.shortlisted)

    client = get_client()

    async with await client.start_session() as session, session.start_transaction():
        now = datetime.now(UTC)

        # 1. Upsert candidate into position's matched list (dedupe by candidate).
        await Position.find_one(Position.id == pos_oid, session=session).update(
            {"$pull": {"matched_candidates": {"candidate_id": cand_oid}}},
            session=session,
        )
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

        # 3. Mirror the move into the dashboard world so the Kanban,
        #    recruiter_ids, and last_activity stay in sync.
        employee_id = await resolve_employee_id(recruiter_id, session=session)
        if opening_id and employee_id:
            existing = await CandidateMapping.find_one(
                CandidateMapping.candidate_id == cand_oid,
                CandidateMapping.job_opening_id == opening_id,
                session=session,
            )
            if existing:
                await existing.set(
                    {
                        "pipeline_stage": target_stage,
                        "employee_id": employee_id,
                        "updated_at": now,
                    },
                    session=session,
                )
            else:
                await CandidateMapping(
                    employee_id=employee_id,
                    candidate_id=cand_oid,
                    job_opening_id=opening_id,
                    pipeline_stage=target_stage,
                ).insert(session=session)

            await JobOpening.find_one(JobOpening.id == opening_id, session=session).update(
                {
                    "$addToSet": {"recruiter_ids": employee_id},
                    "$set": {"last_activity_at": now},
                },
                session=session,
            )

    return profile


async def find_filtered_candidates(
    position_id: str,
    recruiter_id: str | None,
    source: str | None,
    tags: list[str] | None,
    stage: str | None,
    mapped_after: datetime | None,
    mapped_before: datetime | None,
    client_id: str | None = None,
) -> list[dict]:
    """Return the Kanban board for a position: CandidateMapping → Candidate.

    Scoped to the position's linked JobOpening (or `client_id` if supplied, which
    points the board at a specific client opening). Both the unfiltered board and
    every filtered view come through here, so they share one dataset. Returns
    CandidateResponse-compatible dicts plus a `status` (the 3 Kanban columns,
    derived from CandidateMapping.pipeline_stage).
    """
    position = await Position.get(PydanticObjectId(position_id))
    if not position:
        return []

    # Default scope = the position's opening; client_id overrides it.
    opening_id = to_object_id(client_id, "client_id") if client_id else position.job_opening_id
    if not opening_id:
        return []  # position not yet linked to an opening → no pipeline rows

    mapping_match: dict = {"job_opening_id": opening_id}
    if recruiter_id:
        mapping_match["employee_id"] = PydanticObjectId(recruiter_id)
    if stage:
        mapping_match["pipeline_stage"] = stage
    if mapped_after or mapped_before:
        date_filter: dict = {}
        if mapped_after:
            date_filter["$gte"] = mapped_after
        if mapped_before:
            date_filter["$lte"] = mapped_before
        mapping_match["mapped_at"] = date_filter

    candidate_match: dict = {}
    if source:
        candidate_match["source"] = source
    if tags:
        candidate_match["tags"] = {"$all": [t.lower() for t in tags]}

    pipeline: list[dict] = [
        {"$match": mapping_match},
        {
            "$lookup": {
                "from": "candidates",
                "localField": "candidate_id",
                "foreignField": "_id",
                "as": "candidate",
            }
        },
        {"$unwind": "$candidate"},
    ]

    if candidate_match:
        pipeline.append({"$match": {f"candidate.{k}": v for k, v in candidate_match.items()}})

    pipeline.append(
        {
            "$project": {
                "_id": 0,
                "id": {"$toString": "$candidate._id"},
                # Legacy-tolerant: dashboard-shaped docs use full_name/skills/resume_link.
                "name": {
                    "$ifNull": [
                        "$candidate.name",
                        {"$ifNull": ["$candidate.full_name", "Unnamed"]},
                    ]
                },
                "email": "$candidate.email",
                "phone": "$candidate.phone",
                "resume_url": {"$ifNull": ["$candidate.resume_url", "$candidate.resume_link"]},
                "extracted_skills": {
                    "$ifNull": [
                        "$candidate.extracted_skills",
                        {"$ifNull": ["$candidate.skills", []]},
                    ]
                },
                "tags": {"$ifNull": ["$candidate.tags", []]},
                "source": {"$ifNull": ["$candidate.source", "internal"]},
                "cv_link": "$candidate.cv_link",
                # Map the 9 pipeline_stage values onto the 3 Kanban columns.
                "status": {
                    "$switch": {
                        "branches": [
                            {
                                "case": {
                                    "$in": [
                                        "$pipeline_stage",
                                        ["offer_accepted", "joined"],
                                    ]
                                },
                                "then": "accepted",
                            },
                            {
                                "case": {"$in": ["$pipeline_stage", ["rejected", "dropped"]]},
                                "then": "rejected",
                            },
                        ],
                        "default": "pending",
                    }
                },
            }
        }
    )

    collection = CandidateMapping.get_motor_collection()
    return await (await collection.aggregate(pipeline)).to_list(length=None)

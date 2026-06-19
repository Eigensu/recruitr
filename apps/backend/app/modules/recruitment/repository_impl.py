"""Low-level MongoDB operations for the recruitment domain.

All public functions accept a TenantScope and prepend brand_id to every query.
Never call get_motor_collection() outside this module for domain writes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from beanie import PydanticObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.common.utils.object_id import to_object_id
from app.modules.recruitment.enums import (
    TERMINAL_STAGES,
    ActivityType,
    Decision,
    PipelineStage,
)
from app.modules.recruitment.models import (
    ActivityLog,
    Candidate,
    Client,
    Counter,
    Employee,
    Mapping,
    Position,
    StageEvent,
)
from app.modules.recruitment.schemas import TenantScope

# ── Atomic code generation ─────────────────────────────────────────────────────


async def next_seq(brand_id: PydanticObjectId, key: str) -> int:
    """Return the next integer in the per-brand sequence for key.

    Uses findOneAndUpdate($inc) — a single atomic op, safe under concurrency
    without a wrapping transaction.  Gaps are harmless; duplicates are impossible.
    """
    doc = await Counter.get_motor_collection().find_one_and_update(
        {"brand_id": brand_id, "key": key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["seq"])


async def set_seq(brand_id: PydanticObjectId, key: str, value: int) -> None:
    """Set a counter's current value (used by seed/migrate to prevent gaps)."""
    await Counter.get_motor_collection().update_one(
        {"brand_id": brand_id, "key": key},
        {"$set": {"seq": value}},
        upsert=True,
    )


async def generate_client_code(brand_id: PydanticObjectId) -> str:
    seq = await next_seq(brand_id, "client")
    return f"CLI-{seq:03d}"


async def generate_position_code(brand_id: PydanticObjectId, client_code: str) -> str:
    last = await Position.get_motor_collection().find_one(
        {"brand_id": brand_id, "code": {"$regex": f"^{client_code}-POS-"}},
        sort=[("code", -1)],
        projection={"code": 1},
    )
    seq = (int(last["code"].rsplit("-", 1)[-1]) + 1) if last else 1
    return f"{client_code}-POS-{seq:03d}"


# ── Client ─────────────────────────────────────────────────────────────────────


async def get_client(scope: TenantScope, client_id: str) -> Client:
    oid = to_object_id(client_id, "client_id")
    doc = await Client.find_one({"_id": oid, "brand_id": scope.brand_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client not found")
    return doc


async def list_clients(scope: TenantScope) -> list[Client]:
    return await Client.find({"brand_id": scope.brand_id, "is_active": True}).to_list()


# ── Position ───────────────────────────────────────────────────────────────────


async def get_position(scope: TenantScope, position_id: str) -> Position:
    oid = to_object_id(position_id, "position_id")
    doc = await Position.find_one({"_id": oid, "brand_id": scope.brand_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Position not found")
    return doc


async def recompute_position_seats(position_id: PydanticObjectId) -> None:
    """Recalculate filled/remaining seats from terminal-stage mapping count."""
    pipeline = [
        {
            "$match": {
                "position_id": position_id,
                "stage": {
                    "$in": [
                        PipelineStage.offer_accepted.value,
                        PipelineStage.position_close.value,
                    ]
                },
            }
        },
        {"$count": "filled"},
    ]
    result = await (await Mapping.get_motor_collection().aggregate(pipeline)).to_list(None)
    filled = int(result[0]["filled"]) if result else 0

    pos = await Position.get(position_id)
    if pos:
        remaining = max(pos.total_seats - filled, 0)
        update: dict[str, Any] = {
            "filled_seats": filled,
            "remaining_seats": remaining,
            "updated_at": datetime.now(UTC),
        }
        if remaining == 0 and pos.status == "open":
            update["status"] = "closed"
        await Position.get_motor_collection().update_one({"_id": position_id}, {"$set": update})


# ── Candidate ──────────────────────────────────────────────────────────────────


async def get_candidate(scope: TenantScope, candidate_id: str) -> Candidate:
    oid = to_object_id(candidate_id, "candidate_id")
    doc = await Candidate.find_one({"_id": oid, "brand_id": scope.brand_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    return doc


async def update_candidate_current_stage(
    scope: TenantScope, candidate_id: PydanticObjectId, stage: PipelineStage
) -> None:
    """Denormalize the latest pipeline stage onto the candidate document."""
    await Candidate.get_motor_collection().update_one(
        {"_id": candidate_id, "brand_id": scope.brand_id},
        {"$set": {"current_stage": stage.value, "updated_at": datetime.now(UTC)}},
    )


# ── Mapping ────────────────────────────────────────────────────────────────────


async def get_mapping(scope: TenantScope, mapping_id: str) -> Mapping:
    oid = to_object_id(mapping_id, "mapping_id")
    doc = await Mapping.find_one({"_id": oid, "brand_id": scope.brand_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mapping not found")
    return doc


async def create_mapping(
    *,
    scope: TenantScope,
    candidate_id: PydanticObjectId,
    position: Position,
    match_score: float | None,
) -> Mapping:
    """Create a new mapping at the sourced stage.

    Raises 409 if the candidate is already mapped to this position.
    """
    existing = await Mapping.find_one({"candidate_id": candidate_id, "position_id": position.id})
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Candidate is already mapped to this position",
        )
    mapping = Mapping(
        brand_id=scope.brand_id,
        candidate_id=candidate_id,
        position_id=position.id,  # type: ignore[arg-type]
        client_id=position.client_id,
        employee_id=scope.employee_id,
        stage=PipelineStage.sourced,
        decision=Decision.pending,
        match_score=match_score,
        history=[
            StageEvent(
                stage=PipelineStage.sourced,
                decision=Decision.pending,
                by_employee_id=scope.employee_id,
            )
        ],
    )
    await mapping.insert()
    return mapping


async def delete_mapping(mapping: Mapping) -> None:
    await mapping.delete()


async def move_stage(
    *,
    mapping: Mapping,
    new_stage: PipelineStage,
    decision: Decision,
    scope: TenantScope,
) -> Mapping:
    """Transition a mapping to a new pipeline stage.

    Appends a StageEvent to history and updates the denormalized candidate stage.
    Does NOT handle gamification or cache invalidation — caller's responsibility.
    """
    now = datetime.now(UTC)
    event = StageEvent(
        stage=new_stage,
        decision=decision,
        by_employee_id=scope.employee_id,
        at=now,
    )
    await Mapping.get_motor_collection().update_one(
        {"_id": mapping.id},
        {
            "$set": {
                "stage": new_stage.value,
                "decision": decision.value,
                "employee_id": scope.employee_id,
                "updated_at": now,
            },
            "$push": {"history": event.model_dump()},
        },
    )
    mapping.stage = new_stage
    mapping.decision = decision

    # Denormalize onto candidate
    await update_candidate_current_stage(scope, mapping.candidate_id, new_stage)

    # Recompute seats when a terminal stage is reached
    if new_stage in TERMINAL_STAGES:
        await recompute_position_seats(mapping.position_id)

    return mapping


# ── Employee ───────────────────────────────────────────────────────────────────


async def find_employee_by_email(email: str) -> Employee | None:
    return await Employee.find_one({"email": email.lower()})


async def create_employee(
    *,
    name: str,
    email: str,
    user_id: PydanticObjectId | None = None,
    brand_id: PydanticObjectId | None = None,
) -> Employee:
    emp = Employee(name=name, email=email.lower(), user_id=user_id, brand_id=brand_id)
    try:
        await emp.insert()
    except DuplicateKeyError:
        # Race: another request already created it — fetch and return
        existing = await find_employee_by_email(email)
        if existing:
            return existing
        raise
    return emp


async def link_employee_user(employee: Employee, user_id: PydanticObjectId) -> Employee:
    """Stamp user_id on an existing employee (e.g. a seeded employee who just logged in)."""
    if employee.user_id != user_id:
        await Employee.get_motor_collection().update_one(
            {"_id": employee.id},
            {"$set": {"user_id": user_id, "updated_at": datetime.now(UTC)}},
        )
        employee.user_id = user_id
    return employee


# ── Activity log ───────────────────────────────────────────────────────────────


async def log_activity(
    *,
    scope: TenantScope,
    activity_type: ActivityType,
    target_entity_type: str,
    target_entity_id: str,
    description: str,
) -> ActivityLog:
    entry = ActivityLog(
        brand_id=scope.brand_id,
        employee_id=scope.employee_id,
        activity_type=activity_type,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        description=description,
    )
    await entry.insert()
    return entry

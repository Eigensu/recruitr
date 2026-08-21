"""Business logic for the recruitment domain.

Orchestrates repository calls, gamification credits, and cache invalidation.
Gamification is fire-and-forget (best-effort): a duplicate or Redis failure
never rolls back the domain write.
"""

from __future__ import annotations

import logging

from beanie import PydanticObjectId

from app.modules.recruitment.enums import (
    TERMINAL_STAGES,
    ActivityType,
    CandidateEventType,
    Decision,
    PipelineStage,
)
from app.modules.recruitment.models import Employee, Mapping, Position
from app.modules.recruitment.repository import (
    candidate_display_name,
    create_employee,
    delete_mapping,
    find_employee_by_email,
    link_employee_user,
    log_activity,
    recompute_position_seats,
    record_candidate_event,
)
from app.modules.recruitment.repository import (
    create_mapping as repo_create_mapping,
)
from app.modules.recruitment.repository import (
    move_stage as repo_move_stage,
)
from app.modules.recruitment.schemas import TenantScope

logger = logging.getLogger(__name__)

# ── Employee / login linking ───────────────────────────────────────────────────


async def ensure_employee_for_user(user: object) -> Employee:
    """Find or create an Employee record linked to a login User.

    Called on every login and Google OAuth callback so that the Employee
    always exists before the session cookie is issued.

    An employee with no brand yet is auto-assigned the sole existing brand, so
    staff do not have to be onboarded by hand — but only when the address is on
    a configured agency domain. Without that condition this was the whole
    security model: any address that could sign up was handed the workspace and
    read every candidate, position and client in it.
    """
    from app.modules.auth.access import is_agency_email
    from app.modules.brands.models import Brand

    email: str = getattr(user, "email", "")
    name: str = getattr(user, "full_name", None) or email
    user_id: PydanticObjectId = user.id  # type: ignore[assignment]
    role: str = getattr(user, "role", "employee")

    employee = await find_employee_by_email(email)
    if employee is None:
        employee = await create_employee(name=name, email=email, user_id=user_id)
    else:
        employee = await link_employee_user(employee, user_id)

    # Keep role in sync so leaderboard queries can filter without joining users.
    if employee.role != role:
        await Employee.get_motor_collection().update_one(
            {"_id": employee.id}, {"$set": {"role": role}}
        )
        employee.role = role

    if employee.brand_id is None and is_agency_email(email):
        brand = await Brand.find_one({})
        if brand is not None:
            await Employee.get_motor_collection().update_one(
                {"_id": employee.id},
                {"$set": {"brand_id": brand.id}},
            )
            employee.brand_id = brand.id

    return employee


# ── Mapping (positions page drag/drop) ────────────────────────────────────────


async def map_candidate(
    *,
    scope: TenantScope,
    candidate_id: PydanticObjectId,
    position: Position,
    match_score: float | None,
) -> Mapping:
    """Create a mapping at sourced stage, credit recruiter, log activity."""
    mapping = await repo_create_mapping(
        scope=scope,
        candidate_id=candidate_id,
        position=position,
        match_score=match_score,
    )

    # Gamification — fire-and-forget
    await _credit_gamification(scope, mapping, PipelineStage.sourced)

    if scope.is_recruiter:
        await log_activity(
            scope=scope,
            activity_type=ActivityType.mapped,
            target_entity_type="candidate",
            target_entity_id=str(candidate_id),
            description=(
                f"Mapped {await candidate_display_name(candidate_id)} "
                f"to {position.role} @ {position.client_name}"
            ),
        )

    await _invalidate_caches(scope.brand_id)
    return mapping


async def unmap_candidate(*, scope: TenantScope, mapping: Mapping) -> None:
    """Delete a mapping (unmap action), free its seat, log activity, drop caches.

    The permanent history entry is written *before* the delete: the mapping row
    is the only place the position link lives, and once it is gone there is
    nothing left to say which client this candidate was withdrawn from.
    """
    await record_candidate_event(
        scope=scope,
        candidate_id=mapping.candidate_id,
        event_type=CandidateEventType.unmapped,
        position=await Position.get(mapping.position_id),
        from_stage=PipelineStage(mapping.stage) if mapping.stage else None,
    )

    was_terminal = mapping.stage in TERMINAL_STAGES
    await delete_mapping(mapping)

    # A candidate who had accepted or joined was holding a seat, and deleting
    # their mapping is the one way out of a terminal stage that never went
    # through move_stage — so without this the seat stayed filled forever, and
    # a position auto-closed by that last hire could never be reopened for good
    # (recompute would find it still full and close it again).
    # Recomputed after the delete so the count excludes this mapping.
    if was_terminal:
        await recompute_position_seats(mapping.position_id)

    if scope.is_recruiter:
        await log_activity(
            scope=scope,
            activity_type=ActivityType.unmapped,
            target_entity_type="candidate",
            target_entity_id=str(mapping.candidate_id),
            description=(
                f"Unmapped {await candidate_display_name(mapping.candidate_id)} from position"
            ),
        )

    await _invalidate_caches(scope.brand_id)


# ── Pipeline stage moves (Kanban) ─────────────────────────────────────────────


# Maps a target stage to (ActivityType for log, ActivityTypeEnum for gamification)
_STAGE_ACTIVITY: dict[PipelineStage, ActivityType] = {
    PipelineStage.selected: ActivityType.offer_accepted,
    PipelineStage.joined: ActivityType.joined,
    PipelineStage.rejected: ActivityType.rejected,
}

# Maps stage to leaderboard ActivityTypeEnum value
_GAMIFICATION_STAGE: dict[PipelineStage, str] = {
    PipelineStage.sourced: "mapping_completed",
    PipelineStage.selected: "offer_received",
    PipelineStage.joined: "candidate_joined",
    PipelineStage.rejected: "candidate_rejected",
}


async def advance_stage(
    *,
    scope: TenantScope,
    mapping: Mapping,
    new_stage: PipelineStage,
    decision: Decision = Decision.pending,
) -> Mapping:
    """Move a mapping to a new pipeline stage.

    Order of operations (spec §6.4):
    1. DB write (move_stage) — transactional where possible
    2. Gamification credit (idempotent, best-effort)
    3. Activity log
    4. Cache invalidation (post-commit, best-effort)
    """
    mapping = await repo_move_stage(
        mapping=mapping,
        new_stage=new_stage,
        decision=decision,
        scope=scope,
    )

    await _credit_gamification(scope, mapping, new_stage)

    if scope.is_recruiter:
        activity_type = _STAGE_ACTIVITY.get(new_stage, ActivityType.stage_moved)
        await log_activity(
            scope=scope,
            activity_type=activity_type,
            target_entity_type="candidate",
            target_entity_id=str(mapping.candidate_id),
            description=(
                f"Moved {await candidate_display_name(mapping.candidate_id)} "
                f"to {new_stage.value.replace('_', ' ')}"
            ),
        )

    await _invalidate_caches(scope.brand_id)
    return mapping


# ── Internal helpers ───────────────────────────────────────────────────────────


async def _credit_gamification(scope: TenantScope, mapping: Mapping, stage: PipelineStage) -> None:
    """Call leaderboard record_activity_atomic — idempotent, best-effort.

    Skipped for maintainers/admins: they are not recruiters and must never
    appear in the leaderboard or earn an EmployeeStat.
    """
    if not scope.is_recruiter:
        return

    leaderboard_type = _GAMIFICATION_STAGE.get(stage)
    if not leaderboard_type:
        return

    # Import here to avoid circular deps; leaderboard module has no dependency on recruitment
    try:
        from app.modules.leaderboard.enums.activity_type_enum import ActivityTypeEnum
        from app.modules.leaderboard.repository.writes import record_activity_atomic

        activity_ref = f"{mapping.id}:{stage.value}"
        await record_activity_atomic(
            employee_id=str(scope.employee_id),
            candidate_id=str(mapping.candidate_id),
            activity_type=ActivityTypeEnum(leaderboard_type),
            activity_reference_id=activity_ref,
            title=stage.value.replace("_", " ").title(),
            description=f"Candidate pipeline: {stage.value}",
        )
    except Exception:  # noqa: BLE001
        # Gamification failure must never roll back a domain write — but log it,
        # otherwise a systemic write failure stays invisible (as it did when the
        # leaderboard write used an unsupported standalone-Mongo transaction).
        logger.exception(
            "Leaderboard credit failed for employee=%s mapping=%s stage=%s",
            scope.employee_id,
            mapping.id,
            stage.value,
        )


async def _invalidate_caches(brand_id: PydanticObjectId) -> None:
    """Best-effort cache invalidation — always runs after DB commit."""
    try:
        from app.common.extras.redis_cache import dashboard_cache, leaderboard_cache

        await dashboard_cache.delete_pattern("dashboard:*")
        await leaderboard_cache.delete_pattern("leaderboard:*")
    except Exception:  # noqa: BLE001
        pass

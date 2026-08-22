"""Referee API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.common.utils.object_id import to_object_id
from app.dependencies import get_current_user
from app.modules.auth.models import User, UserRole
from app.modules.auth.schemas import TokenPayload
from app.modules.dashboard import referee_service
from app.modules.recruitment.enums import Decision, PipelineStage
from app.modules.recruitment.models import Mapping, RefereeUser, ReferralRecord
from app.modules.recruitment.repository_impl import move_stage
from app.modules.recruitment.schemas import TenantScope
from app.modules.storage import service as storage_service
from app.modules.storage.uploads import read_offer_letter

router = APIRouter(prefix="/api/v1/referee-dashboard", tags=["Referee Dashboard"])


async def get_current_referee(
    current_user: Annotated[TokenPayload, Depends(get_current_user)],
) -> User:
    from beanie import PydanticObjectId

    user = await User.get(PydanticObjectId(current_user.sub))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    if user.role != UserRole.referee:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Access denied: only referees can access the referee portal."
        )

    return user


async def get_referee_grant(user: User):
    from app.modules.auth.access import find_referee_authorization

    grant = await find_referee_authorization(user.email)
    if grant is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Referee grant missing or inactive.")
    return grant


@router.get("/summary")
async def get_summary(user: Annotated[User, Depends(get_current_referee)]):
    grant = await get_referee_grant(user)

    # Calculate Eligibility First
    await referee_service.update_eligibility_and_incentives(grant.brand_id, grant.id)

    summary = await referee_service.get_dashboard_summary(grant.brand_id, grant.id)
    return summary


@router.get("/referrals")
async def get_referrals(user: Annotated[User, Depends(get_current_referee)]):
    grant = await get_referee_grant(user)

    # Open any ledger entry this referee is still missing before reading. The
    # portal happens to load /summary alongside this, which would also do it, but
    # a referral that accrues nothing until a sibling endpoint is called is a
    # coupling worth not having. Deliberately only the backfill, not
    # update_eligibility_and_incentives — see the note in get_referrals.
    await referee_service.backfill_missing_referral_records(grant.brand_id, grant.id)

    referrals = await referee_service.get_referrals(grant.brand_id, grant.id)
    return referrals


@router.get("/payments")
async def get_payments(user: Annotated[User, Depends(get_current_referee)]):
    grant = await get_referee_grant(user)

    from app.modules.recruitment.models import PaymentBatch

    batches = await PaymentBatch.find(
        {"brand_id": grant.brand_id, "referee_id": grant.id}
    ).to_list()

    return [
        {
            "batch_id": b.batch_id,
            "cycle_month": b.cycle_month,
            "total_amount": b.total_amount,
            "paid_on": b.paid_on,
            "payment_reference": b.payment_reference,
        }
        for b in batches
    ]


# ── Referral actions ──────────────────────────────────────────────────────────

# The moves a referee may make on their own referral. Deliberately the same two
# decision points the client gets in recruitment/controller/pipeline.py: a stage
# absent as a key here exposes no buttons and refuses every move, so a stage
# added to PipelineStage later stays closed to referees until someone opts it in
# here on purpose.
_ALLOWED_TRANSITIONS: dict[str, tuple[PipelineStage, ...]] = {
    PipelineStage.sent_to_client.value: (PipelineStage.interview, PipelineStage.rejected),
    PipelineStage.interview.value: (PipelineStage.selected, PipelineStage.rejected),
}


class RefereeStageMoveRequest(BaseModel):
    new_stage: PipelineStage


async def _own_referral_or_404(
    grant: RefereeUser, mapping_id: str
) -> tuple[ReferralRecord, Mapping]:
    """Resolve a mapping this referee actually referred, or 404.

    Ownership is proved through ReferralRecord rather than through the Mapping,
    because none of the usual narrowing applies to a referee: they have no
    Employee record and no client_id, so both TenantScope.scoped() and
    scope_mapping_match() leave a query untouched for them. Requiring a referral
    row carrying this referee_id *and* this brand_id is the only thing standing
    between a referee and every other referral in the brand — a bare
    Mapping.get(mapping_id) here would hand over the whole pipeline.

    404 rather than 403 on a referral belonging to someone else: whether a given
    mapping id exists is itself not the referee's to know.
    """
    oid = to_object_id(mapping_id, "mapping_id")
    referral = await ReferralRecord.find_one(
        {"brand_id": grant.brand_id, "referee_id": grant.id, "mapping_id": oid}
    )
    if referral is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral not found")

    mapping = await Mapping.get(oid)
    if mapping is None or mapping.brand_id != grant.brand_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral not found")

    return referral, mapping


def _referee_scope(grant: RefereeUser) -> TenantScope:
    """A write scope for the referee: their brand, with no employee identity.

    employee_id stays None on purpose so move_stage leaves Mapping.employee_id
    pointing at the recruiter who actually worked the candidate rather than
    blanking a required field (see move_stage's docstring).
    """
    return TenantScope(brand_id=grant.brand_id, employee_id=None, role=UserRole.referee)


@router.post("/referrals/{mapping_id}/move")
async def move_own_referral(
    mapping_id: str,
    req: RefereeStageMoveRequest,
    user: Annotated[User, Depends(get_current_referee)],
):
    """Advance or reject a candidate the signed-in referee referred."""
    grant = await get_referee_grant(user)
    referral, mapping = await _own_referral_or_404(grant, mapping_id)

    current = mapping.stage.value if isinstance(mapping.stage, PipelineStage) else mapping.stage

    if req.new_stage.value == current:
        # Already there — treat a double-click as success rather than a 403.
        return {"success": True, "stage": current, "kanban_stage": referral.kanban_stage}

    if req.new_stage not in _ALLOWED_TRANSITIONS.get(current, ()):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"A referee cannot move a referral from {current} to {req.new_stage.value}.",
        )

    await move_stage(
        mapping=mapping,
        new_stage=req.new_stage,
        decision=(
            Decision.rejected if req.new_stage == PipelineStage.rejected else Decision.pending
        ),
        scope=_referee_scope(grant),
        actor="referee",
    )

    # Pull the referee-facing tracker back in line with the mapping just moved,
    # so the portal reflects the click now instead of at the next 15-minute
    # poll. Rejections deliberately leave kanban_stage where it was — see
    # sync_referral_with_mapping's closed-stage skip list.
    await referee_service.sync_referral_with_mapping(referral)

    return {
        "success": True,
        "stage": req.new_stage.value,
        "kanban_stage": referral.kanban_stage,
    }


@router.put("/referrals/{mapping_id}/offer-letter")
async def upload_own_referral_offer(
    mapping_id: str,
    user: Annotated[User, Depends(get_current_referee)],
    file: Annotated[UploadFile, File(description="Offer letter PDF")],
):
    """Attach an offer letter to a referral the signed-in referee owns."""
    grant = await get_referee_grant(user)
    _, mapping = await _own_referral_or_404(grant, mapping_id)

    if mapping.stage != PipelineStage.selected.value:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "An offer letter can only be uploaded once the candidate is selected.",
        )

    file_bytes, filename = await read_offer_letter(file)
    result = storage_service.upload_offer_letter(file_bytes, filename)
    mapping.offer_letter_url = result.get("secure_url")
    await mapping.save()

    return {"success": True, "offer_letter_url": mapping.offer_letter_url}

"""Referee API endpoints.

Read-only by design. A referee sees where their referrals have got to and what
they are owed; moving a candidate is the recruiter's call on the recruitment
pipeline, or the client's on theirs. There are deliberately no write endpoints
here — the portal must not be a third place a stage can change from.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.modules.auth.models import User, UserRole
from app.modules.auth.schemas import TokenPayload
from app.modules.dashboard import referee_service

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

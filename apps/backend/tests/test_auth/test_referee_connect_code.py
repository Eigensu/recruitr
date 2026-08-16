"""Referee grants written before connect codes existed.

Pins the failure this reproduced in production: connect_code landed on
RefereeUser as a required field, every sign-in loads the grant through
find_referee_authorization, and the rows already in the collection had no such
field — so pydantic refused to parse them and login 500'd for those referees
rather than failing any check they could act on.
"""

from beanie import PydanticObjectId

from app.modules.auth.access import find_referee_authorization
from app.modules.recruitment.enums import PaymentStatus, RefereeKanbanStage
from app.modules.recruitment.models import RefereeUser, ReferralRecord
from app.modules.recruitment.utils.connect_code import ensure_connect_code, generate_connect_code

BRAND_ID = PydanticObjectId()
LEGACY_EMAIL = "legacy.referee@example.com"


async def _insert_legacy_referee(email: str = LEGACY_EMAIL) -> PydanticObjectId:
    """Write a grant straight to Mongo with connect_code absent, as prod has."""
    collection = RefereeUser.get_motor_collection()
    result = await collection.insert_one(
        {
            "brand_id": BRAND_ID,
            "email": email,
            "name": "Legacy Referee",
            "role": "referee",
            "is_active": True,
        }
    )
    return result.inserted_id


async def test_grant_without_connect_code_still_loads() -> None:
    await _insert_legacy_referee()

    grant = await find_referee_authorization(LEGACY_EMAIL)

    assert grant is not None
    assert grant.connect_code is None


async def test_ensure_connect_code_mints_and_persists_one() -> None:
    oid = await _insert_legacy_referee()

    grant = await find_referee_authorization(LEGACY_EMAIL)
    code = await ensure_connect_code(grant)

    assert code is not None
    assert len(code) == 8
    reloaded = await RefereeUser.get(oid)
    assert reloaded.connect_code == code


async def test_ensure_connect_code_is_idempotent() -> None:
    await _insert_legacy_referee()

    first = await ensure_connect_code(await find_referee_authorization(LEGACY_EMAIL))
    second = await ensure_connect_code(await find_referee_authorization(LEGACY_EMAIL))

    assert first == second


async def test_several_legacy_grants_coexist() -> None:
    """The unique index on connect_code is partial for this: a plain one would
    treat every codeless row as a duplicate of the first."""
    await _insert_legacy_referee("one@example.com")
    await _insert_legacy_referee("two@example.com")

    assert await RefereeUser.find({"connect_code": None}).count() == 2


async def test_generated_codes_avoid_ambiguous_characters() -> None:
    """O/0 and I/1/L are excluded — the code gets copied off a screen."""
    codes = "".join(generate_connect_code() for _ in range(200))

    assert not set(codes) & set("O0I1L")


async def test_new_referral_defaults_to_a_status_the_payment_jobs_select_on() -> None:
    """A referral defaulted to an off-enum spelling is never priced or paid.

    update_eligibility_and_incentives and the nightly job both select on
    {"$in": [PaymentStatus.pending.value, PaymentStatus.owed.value]}, so a
    default of "PENDING" would drop every new referral out of both.
    """
    record = ReferralRecord(
        brand_id=BRAND_ID,
        referee_id=PydanticObjectId(),
        mapping_id=PydanticObjectId(),
        candidate_id=PydanticObjectId(),
        position_id=PydanticObjectId(),
    )
    await record.insert()

    unpaid = await ReferralRecord.find(
        {"payment_status": {"$in": [PaymentStatus.pending.value, PaymentStatus.owed.value]}}
    ).to_list()

    assert [r.id for r in unpaid] == [record.id]
    assert record.kanban_stage == RefereeKanbanStage.cv_received.value

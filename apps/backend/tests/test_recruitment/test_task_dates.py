"""A checklist's start date: chosen by the creator, never before today.

The form used to have no start-date input at all — every task silently started
at the moment it was created. It now takes one, and the rule is "today or
later", checked without knowing the creator's timezone (see
starts_in_the_past). The payloads below are what an IST browser sends: local
midnight, which is 18:30Z the previous UTC day.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from beanie import PydanticObjectId
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user_doc, get_tenant, get_viewer
from app.core.main import app
from app.modules.auth.models import UserRole
from app.modules.recruitment.enums.activity_type import ActivityType
from app.modules.recruitment.models import (
    ActivityLog,
    Employee,
    RecruitmentTask,
    TaskAssignmentType,
)
from app.modules.recruitment.schemas import TenantScope
from app.modules.recruitment.schemas.tasks import starts_in_the_past

_BRAND = PydanticObjectId()
_ADMIN_EMP = PydanticObjectId()
_SCOPE = TenantScope(brand_id=_BRAND, employee_id=_ADMIN_EMP, role=UserRole.maintainer)
_USER = SimpleNamespace(id=PydanticObjectId(), role=UserRole.maintainer, email="m@test.com")

_IST = timedelta(hours=5, minutes=30)
_URL = "/api/v1/tasks/"


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _ist_midnight(days_from_today: int = 0) -> datetime:
    """Local midnight in IST, as the naive-UTC instant the browser's ISO string encodes."""
    ist_now = _now() + _IST
    midnight = ist_now.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(days=days_from_today) - _IST


def _iso(dt: datetime) -> str:
    return dt.replace(tzinfo=UTC).isoformat()


def _payload(start: datetime, due: datetime) -> dict:
    return {
        "title": "Map 10 candidates",
        "tracked_activity_type": "mapped",
        "target_count": 10,
        "assignee_type": "all",
        "start_date": _iso(start),
        "due_date": _iso(due),
    }


@pytest_asyncio.fixture
async def api(init_test_db):
    app.dependency_overrides[get_tenant] = lambda: _SCOPE
    app.dependency_overrides[get_viewer] = lambda: _USER
    app.dependency_overrides[get_current_user_doc] = lambda: _USER
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _task(start: datetime, due: datetime, **kw) -> RecruitmentTask:
    task = RecruitmentTask(
        brand_id=_BRAND,
        title="t",
        tracked_activity_type=ActivityType.mapped,
        target_count=5,
        assignee_type=kw.pop("assignee_type", TaskAssignmentType.all),
        start_date=start,
        due_date=due,
        **kw,
    )
    await task.insert()
    return task


# ── The 24-hour rule itself ────────────────────────────────────────────────────


@pytest.mark.no_db
def test_a_start_less_than_a_day_ago_is_today():
    assert not starts_in_the_past(_now() - timedelta(hours=23, minutes=59))


@pytest.mark.no_db
def test_a_start_a_full_day_ago_is_yesterday():
    assert starts_in_the_past(_now() - timedelta(hours=24, seconds=1))


@pytest.mark.no_db
def test_a_future_start_is_fine():
    assert not starts_in_the_past(_now() + timedelta(days=3))


@pytest.mark.no_db
def test_an_aware_datetime_is_compared_in_utc():
    """The API receives aware datetimes; the rule must not trip over the offset."""
    ist = datetime.now(UTC).astimezone(ZoneInfo("Asia/Kolkata"))
    assert not starts_in_the_past(ist.replace(hour=0, minute=0, second=0, microsecond=0))


# ── Create ─────────────────────────────────────────────────────────────────────


async def test_create_starting_today_in_ist(api):
    """Today's IST midnight is the previous UTC day — it must still count as today."""
    res = await api.post(_URL, json=_payload(_ist_midnight(0), _ist_midnight(1)))

    assert res.status_code == 200, res.text
    stored = await RecruitmentTask.get(res.json()["id"])
    assert stored.start_date == _ist_midnight(0)


async def test_create_starting_later(api):
    res = await api.post(_URL, json=_payload(_ist_midnight(3), _ist_midnight(10)))

    assert res.status_code == 200, res.text
    assert (await RecruitmentTask.get(res.json()["id"])).start_date == _ist_midnight(3)


async def test_create_starting_yesterday_is_refused(api):
    res = await api.post(_URL, json=_payload(_ist_midnight(-1), _ist_midnight(1)))

    assert res.status_code == 422
    assert "earlier than today" in res.text
    assert await RecruitmentTask.find_all().count() == 0


async def test_create_due_before_start_is_still_refused(api):
    res = await api.post(_URL, json=_payload(_ist_midnight(5), _ist_midnight(2)))

    assert res.status_code == 422


# ── Update ─────────────────────────────────────────────────────────────────────


async def test_a_task_that_has_not_started_can_move_its_start(api):
    task = await _task(_ist_midnight(2), _ist_midnight(9))

    res = await api.patch(f"{_URL}{task.id}", json={"start_date": _iso(_ist_midnight(4))})

    assert res.status_code == 200, res.text
    assert (await RecruitmentTask.get(task.id)).start_date == _ist_midnight(4)


async def test_a_task_that_has_not_started_cannot_move_into_the_past(api):
    task = await _task(_ist_midnight(2), _ist_midnight(9))

    res = await api.patch(f"{_URL}{task.id}", json={"start_date": _iso(_ist_midnight(-2))})

    assert res.status_code == 400
    assert (await RecruitmentTask.get(task.id)).start_date == _ist_midnight(2)


async def test_a_started_task_cannot_move_its_start(api):
    task = await _task(_ist_midnight(-3), _ist_midnight(4))

    res = await api.patch(f"{_URL}{task.id}", json={"start_date": _iso(_ist_midnight(1))})

    assert res.status_code == 400
    assert "started" in res.text
    assert (await RecruitmentTask.get(task.id)).start_date == _ist_midnight(-3)


async def test_a_started_task_can_still_change_everything_else(api):
    """Resending the unchanged start (or omitting it) must not trip the lock."""
    task = await _task(_ist_midnight(-3), _ist_midnight(4))

    res = await api.patch(
        f"{_URL}{task.id}",
        json={"start_date": _iso(_ist_midnight(-3)), "due_date": _iso(_ist_midnight(8))},
    )
    assert res.status_code == 200, res.text

    res = await api.patch(f"{_URL}{task.id}", json={"target_count": 7})
    assert res.status_code == 200, res.text

    stored = await RecruitmentTask.get(task.id)
    assert stored.due_date == _ist_midnight(8)
    assert stored.target_count == 7


# ── Counting stays inside the window ───────────────────────────────────────────


async def test_only_activity_inside_the_window_counts(api):
    recruiter = Employee(brand_id=_BRAND, name="Rae", email="rae@test.com")
    await recruiter.insert()
    start, due = _ist_midnight(-5), _ist_midnight(-1) - timedelta(milliseconds=1)
    task = await _task(
        start, due, assignee_type=TaskAssignmentType.single, assignee_id=recruiter.id
    )

    for at in (
        start - timedelta(minutes=1),  # before the window
        start,  # first instant
        start + timedelta(days=2),
        due,  # last instant
        due + timedelta(minutes=1),  # after the window
    ):
        await ActivityLog(
            brand_id=_BRAND,
            employee_id=recruiter.id,
            activity_type=ActivityType.mapped,
            target_entity_type="candidate",
            target_entity_id="x",
            description="mapped",
            created_at=at,
        ).insert()

    res = await api.get(_URL)

    assert res.status_code == 200, res.text
    [row] = [t for t in res.json() if t["id"] == str(task.id)]
    assert row["completed_count"] == 3

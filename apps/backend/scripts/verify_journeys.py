"""End-to-end runtime gate: seed the DB and run the four acceptance journeys,
asserting persisted database state at each step.

This is the *real* gate (static checks cannot catch runtime data-shape issues).
Requires a running MongoDB replica set (transactions are used by /match).

Usage (from apps/backend, with backend deps installed and MONGODB_URI set):
    python -m scripts.verify_journeys            # seed + run all journeys
    python -m scripts.verify_journeys --no-seed  # run against existing data

Exit code 0 = all journeys passed; non-zero = a journey failed.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

from beanie import PydanticObjectId

from app.database import init_db
from app.modules.auth.models import User
from app.modules.candidates import service as cand_service
from app.modules.candidates.models import Candidate
from app.modules.candidates.schemas import CandidateCreate, CandidateListFilters
from app.modules.dashboard.models import CandidateMapping, JobOpening
from app.modules.dashboard.repository import fetch_client_profiles
from app.modules.dashboard.seed import seed_dashboard_data
from app.modules.pipeline import service as pipe_service
from app.modules.positions.models import Position

_PASS = "\033[92mPASS\033[0m"
_FAIL = "\033[91mFAIL\033[0m"


async def _journey_4_no_500s() -> None:
    """Seed DB → directory + board + client filter return data, not 500s."""
    # Directory: parses the (possibly legacy) candidates collection through the unified model.
    candidates = await cand_service.list_candidates(CandidateListFilters(page=1, limit=50))
    assert candidates, "directory returned no candidates"
    assert all(c.name for c in candidates), "a candidate parsed without a name"

    # Board scoped to a SEEDED opening that has mappings (the old 500 trigger / Client filter).
    opening_ids = await CandidateMapping.get_motor_collection().distinct("job_opening_id")
    assert opening_ids, "no seeded mappings to scope a board against"
    opening_id = opening_ids[0]
    position = Position(
        brand_id=PydanticObjectId(), title="Verify Position", job_opening_id=opening_id
    )
    await position.insert()

    rows = await pipe_service.find_filtered_candidates(
        position_id=str(position.id),
        recruiter_id=None,
        source=None,
        tags=None,
        stage=None,
        mapped_after=None,
        mapped_before=None,
        client_id=str(opening_id),
    )
    assert rows, "board returned no rows for a seeded opening"
    assert all(r.get("name") for r in rows), "a board row is missing name (would 500)"
    print(
        f"  {_PASS} Journey 4 — directory + board + client filter: no 500s "
        f"({len(candidates)} candidates, {len(rows)} board rows)"
    )
    await position.delete()


async def _journey_1_add_candidate() -> Candidate:
    """Add Candidate → appears in directory."""
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    email = f"verify.{stamp}@journeys.test"
    created = await cand_service.create_candidate(
        CandidateCreate(name="Verify Candidate", email=email, source="internal", tags=["verify"])
    )
    found = await cand_service.list_candidates(CandidateListFilters(search=email, page=1, limit=5))
    assert any(c.email == email for c in found), "new candidate not found in directory"
    print(f"  {_PASS} Journey 1 — add candidate → appears in directory ({email})")
    return created


async def _journey_2_3_assign_drag(candidate: Candidate) -> None:
    """Assign → Pending → drag to Accepted → persists; recruiter + client profile update."""
    stamp = datetime.now(UTC).strftime("%H%M%S%f")
    user = User(email=f"recruiter.{stamp}@journeys.test", full_name="Verify Recruiter")
    await user.insert()
    position = Position(brand_id=PydanticObjectId(), title="Verify Pipeline", requirements=["pos"])
    await position.insert()

    # Assign (Pending)
    await pipe_service.match_candidate_to_position(
        position_id=str(position.id),
        candidate_id=str(candidate.id),
        recruiter_id=str(user.id),
        target_status="pending",
    )
    position = await Position.get(position.id)
    assert position.job_opening_id, "position was not linked to a JobOpening"
    mapping = await CandidateMapping.find_one(
        CandidateMapping.candidate_id == candidate.id,
        CandidateMapping.job_opening_id == position.job_opening_id,
    )
    assert mapping is not None, "CandidateMapping not created on assign"

    board = await pipe_service.find_filtered_candidates(
        position_id=str(position.id),
        recruiter_id=None,
        source=None,
        tags=None,
        stage=None,
        mapped_after=None,
        mapped_before=None,
    )
    assert any(r["id"] == str(candidate.id) and r["status"] == "pending" for r in board), (
        "assigned candidate not in Pending"
    )
    print(f"  {_PASS} Journey 2a — assign → candidate in Pending")

    # Drag to Accepted → persists
    await pipe_service.match_candidate_to_position(
        position_id=str(position.id),
        candidate_id=str(candidate.id),
        recruiter_id=str(user.id),
        target_status="accepted",
    )
    board = await pipe_service.find_filtered_candidates(
        position_id=str(position.id),
        recruiter_id=None,
        source=None,
        tags=None,
        stage=None,
        mapped_after=None,
        mapped_before=None,
    )
    assert any(r["id"] == str(candidate.id) and r["status"] == "accepted" for r in board), (
        "drag to Accepted did not persist"
    )
    print(f"  {_PASS} Journey 2b — drag to Accepted persists after reload")

    # Journey 3 — recruiter recorded + client profile updated
    opening = await JobOpening.get(position.job_opening_id)
    assert opening.recruiter_ids, "JobOpening.recruiter_ids not populated"
    assert opening.last_activity_at is not None, "last_activity_at not stamped"

    profiles = await fetch_client_profiles(page=1, limit=200)
    row = next((r for r in profiles["items"] if r["client_name"] == opening.client_name), None)
    assert row is not None, "client profile row missing"
    assert row["active_recruiters"] >= 1, "Active Recruiters did not become > 0"
    assert row["last_activity"] is not None, "Last Activity did not populate"
    print(
        f"  {_PASS} Journey 3 — recruiter recorded; Active Recruiters={row['active_recruiters']}, "
        f"Last Activity set"
    )

    # Cleanup
    await CandidateMapping.find(CandidateMapping.candidate_id == candidate.id).delete()
    await position.delete()
    await user.delete()
    await candidate.delete()


async def _run(seed: bool) -> int:
    await init_db()
    if seed:
        print("Seeding dashboard data…")
        await seed_dashboard_data(reset=True)
    print("\nRunning acceptance journeys:")
    try:
        await _journey_4_no_500s()
        cand = await _journey_1_add_candidate()
        await _journey_2_3_assign_drag(cand)
    except AssertionError as exc:
        print(f"  {_FAIL} {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"  {_FAIL} unexpected error: {exc!r}")
        if "Transaction numbers" in str(exc) or "replica set" in str(exc).lower():
            print("  (hint: /match needs a MongoDB replica set — use docker-compose's mongo)")
        return 1
    print("\nAll journeys passed ✅")
    return 0


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run end-to-end acceptance journeys")
    parser.add_argument("--no-seed", action="store_true", help="Do not (re)seed before running")
    args = parser.parse_args()
    sys.exit(await _run(seed=not args.no_seed))


if __name__ == "__main__":
    asyncio.run(_main())

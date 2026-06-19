"""One-time leaderboard repair/migration for prod.

Why this exists (state found 2026-06-19):
  - The gamification write silently failed for a long time, so `recruiter_activity`
    was empty and `employee_stats` held stale, hand-/seed-set values whose `level`
    did not match XP under any formula.
  - 5 of 9 `employee_stats` rows are GHOSTS: their `employee_id` exists only in
    seeded `candidate_mappings`, not in `employees` — so they never render but sit
    in the DB as junk. The seeded `leaderboard_history` scores don't match real stats.

What each step does:
  stats    Rebuild every employee_stats row from the real candidate_mappings
           (absolute XP + level via the new curve) and recompute ranks. Reuses
           the app's backfill_stats_from_mappings(). Idempotent (upsert).
  cleanup  Delete leaderboard rows (employee_stats, leaderboard_history,
           recruiter_activity) for ghost employee_ids (no matching employees doc)
           and for admin/maintainer employees (they must never be on the board),
           then re-rank the survivors. Scoped to leaderboard collections only —
           it never touches candidate_mappings / positions / the recruitment domain.
  history  Snapshot the current month into leaderboard_history for the surviving
           real recruiters so the monthly-growth chart reflects reality.
  activity Backfill recruiter_activity (the "Live actions" feed) for real
           recruiters from each mapping's stage history, using the same
           activity_reference_id scheme as the live path so later live writes
           dedup via the unique index. Feed-only — does not touch employee_stats.

SAFETY: dry-run by default — prints what it WOULD do and writes nothing. Pass
--apply to actually mutate. Uses settings.MONGODB_URI (the prod Atlas cluster from
.env) unless --uri is given.

Usage:
    cd apps/backend
    python -m scripts.migrate_leaderboard            # dry run, all steps
    python -m scripts.migrate_leaderboard --apply     # execute all steps
    python -m scripts.migrate_leaderboard --apply --steps stats,cleanup
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from pymongo.errors import DuplicateKeyError

from app.database import init_db
from app.modules.leaderboard.enums import ActivityTypeEnum
from app.modules.leaderboard.models import (
    EmployeeStat,
    LeaderboardHistory,
    RecruiterActivity,
)
from app.modules.leaderboard.repository.writes import (
    backfill_stats_from_mappings,
    create_monthly_snapshots,
    recompute_ranks,
)
from app.modules.leaderboard.utils.ranking_calculator import activity_points
from app.modules.recruitment.models import Employee, Mapping

ALL_STEPS = ("stats", "cleanup", "history", "activity")

# Pipeline stage -> leaderboard activity type (mirrors recruitment _GAMIFICATION_STAGE).
GAMIFY_STAGE: dict[str, str] = {
    "sourced": ActivityTypeEnum.MAPPING_COMPLETED.value,
    "offer": ActivityTypeEnum.OFFER_RECEIVED.value,
    "position_close": ActivityTypeEnum.CANDIDATE_JOINED.value,
    "rejected": ActivityTypeEnum.CANDIDATE_REJECTED.value,
}


async def _partition_stats() -> tuple[set, set, set, dict]:
    """Return (real_recruiter_ids, kept_other_ids, removable_ids, name_by_id).

    real_recruiter_ids  — real, non-admin/maintainer employees (the genuine
                          leaderboard; the only ones that get a feed backfill).
    kept_other_ids      — admin/maintainer employees: their rows are KEPT (the
                          read path already filters them off the board), but they
                          are excluded from the activity feed.
    removable_ids       — ghost ids (no employees doc) — deleted.
    """
    emp_coll = Employee.get_motor_collection()
    employees = {e["_id"]: e for e in await emp_coll.find({}).to_list(length=None)}
    stat_ids = await EmployeeStat.get_motor_collection().distinct("employee_id")

    real: set = set()
    kept_other: set = set()
    removable: set = set()
    names: dict = {}
    for sid in stat_ids:
        emp = employees.get(sid)
        if emp is None:
            removable.add(sid)
            names[sid] = "??? (ghost — no employees doc)"
        elif emp.get("role") in {"admin", "maintainer"}:
            kept_other.add(sid)
            names[sid] = f"{emp.get('name')} (role={emp.get('role')})"
        else:
            real.add(sid)
            names[sid] = emp.get("name")
    return real, kept_other, removable, names


async def _build_activity_events(real_ids: set) -> list[dict]:
    """One feed event per (mapping, gamified stage) reached, from stage history."""
    events: list[dict] = []
    cursor = Mapping.get_motor_collection().find({"employee_id": {"$in": list(real_ids)}})
    for m in await cursor.to_list(length=None):
        mid, eid, cid = m["_id"], m["employee_id"], m.get("candidate_id")
        seen: set[str] = set()
        history = m.get("history") or []
        for entry in [*history, {"stage": m.get("stage"), "at": m.get("updated_at")}]:
            stage = entry.get("stage")
            if stage not in GAMIFY_STAGE or stage in seen:
                continue
            seen.add(stage)
            events.append(
                {
                    "employee_id": eid,
                    "candidate_id": cid,
                    "activity_type": GAMIFY_STAGE[stage],
                    "title": stage.replace("_", " ").title(),
                    "description": f"Candidate pipeline: {stage}",
                    "points_earned": activity_points(ActivityTypeEnum(GAMIFY_STAGE[stage])),
                    "activity_reference_id": f"{mid}:{stage}",
                    "created_at": entry.get("at") or m.get("mapped_at") or datetime.now(UTC),
                }
            )
    return events


async def run(*, apply: bool, steps: tuple[str, ...]) -> None:
    await init_db()
    real, kept_other, removable, names = await _partition_stats()

    print(f"\n{'APPLY' if apply else 'DRY-RUN'} — steps: {', '.join(steps)}")
    print(
        f"\nemployee_stats: {len(real)} real recruiter(s), "
        f"{len(kept_other)} kept (off-board), {len(removable)} removable"
    )
    for sid in removable:
        print(f"  - delete:    {names.get(sid)}  [{sid}]")
    for sid in kept_other:
        print(f"  - keep/off:  {names.get(sid)}  [{sid}]")
    for sid in real:
        print(f"  - keep:      {names.get(sid)}  [{sid}]")

    if "stats" in steps:
        if apply:
            n = await backfill_stats_from_mappings()
            print(f"\n[stats] rebuilt employee_stats from {n} mapped recruiter group(s)")
        else:
            n = len(await Mapping.get_motor_collection().distinct("employee_id"))
            print(f"\n[stats] would rebuild stats/levels/ranks from {n} recruiter group(s)")

    if "cleanup" in steps:
        flt = {"employee_id": {"$in": list(removable)}}
        if apply and removable:
            d1 = (await EmployeeStat.get_motor_collection().delete_many(flt)).deleted_count
            d2 = (await LeaderboardHistory.get_motor_collection().delete_many(flt)).deleted_count
            d3 = (await RecruiterActivity.get_motor_collection().delete_many(flt)).deleted_count
            await recompute_ranks()
            print(f"[cleanup] deleted stats={d1} history={d2} activity={d3}; re-ranked survivors")
        else:
            es = await EmployeeStat.get_motor_collection().count_documents(flt)
            lh = await LeaderboardHistory.get_motor_collection().count_documents(flt)
            ra = await RecruiterActivity.get_motor_collection().count_documents(flt)
            print(f"[cleanup] would delete stats={es} history={lh} activity={ra} (ghosts/admins)")

    if "history" in steps:
        month = datetime.now(UTC).strftime("%Y-%m")
        if apply:
            n = await create_monthly_snapshots(month)
            print(f"[history] snapshotted {n} stat row(s) into leaderboard_history for {month}")
        else:
            print(f"[history] would snapshot current real stats into month {month}")

    if "activity" in steps:
        events = await _build_activity_events(real)
        if apply:
            inserted = 0
            for ev in events:
                try:
                    await RecruiterActivity.get_motor_collection().insert_one(ev)
                    inserted += 1
                except DuplicateKeyError:
                    pass
            print(
                f"[activity] inserted {inserted}/{len(events)} feed event(s) (rest already existed)"
            )
        else:
            print(f"[activity] would create up to {len(events)} recruiter_activity feed event(s)")

    print("\nDone." + ("" if apply else "  (dry-run — nothing written)"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair/migrate leaderboard data.")
    parser.add_argument("--apply", action="store_true", help="Execute writes (default: dry-run)")
    parser.add_argument(
        "--steps",
        default=",".join(ALL_STEPS),
        help=f"Comma-separated subset of: {','.join(ALL_STEPS)}",
    )
    args = parser.parse_args()
    steps = tuple(s.strip() for s in args.steps.split(",") if s.strip() in ALL_STEPS)
    asyncio.run(run(apply=args.apply, steps=steps))


if __name__ == "__main__":
    main()

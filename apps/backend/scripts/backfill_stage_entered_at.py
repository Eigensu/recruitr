"""Recover when a mapping entered the stage it is sitting in now.

Usage (from apps/backend):
    python3 scripts/backfill_stage_entered_at.py            # dry run
    python3 scripts/backfill_stage_entered_at.py --confirm  # apply

The board's "days in stage" badge reads Mapping.history, which move_stage
appends to on every transition. Rows whose stage was set directly — seeded
data, and anything migrated by migrate_old_pipeline_stages.py — never got that
event, so their history holds only the stage they came *from* and the badge
falls back to mapped_at. It then reads "days since first mapped": a candidate
mapped in March shows months in a stage they entered last week.

candidate_events is the permanent log and did record those transitions, with
to_stage and a timestamp. This copies the newest matching one back onto the
mapping as a StageEvent so the badge — and the referee portal's joining_date
lookup, which scans the same array — resolve correctly.

Only mappings with no history event for their current stage are touched, so
re-running is a no-op. Rows candidate_events cannot explain are reported and
left alone: mapped_at remains the honest answer for those.

Take a backup first:
    mongodump --uri "$MONGODB_URI" --db <db> --collection candidate_mappings
"""

import argparse
import pathlib
import sys
from collections import Counter

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient  # noqa: E402

from app.config import settings  # noqa: E402


def _needs_backfill(mapping: dict) -> bool:
    """True when nothing in history records the mapping's current stage."""
    stage = mapping.get("stage")
    return not any(event.get("stage") == stage for event in mapping.get("history") or [])


def plan(db) -> tuple[list[tuple], list[dict]]:
    """Work out which mappings can be repaired, and from which event.

    Returns (planned, unexplained). Reads only.
    """
    every = list(
        db.candidate_mappings.find(
            {}, {"stage": 1, "history": 1, "candidate_id": 1, "mapped_at": 1}
        )
    )
    planned: list[tuple] = []
    unexplained: list[dict] = []

    for m in (m for m in every if _needs_backfill(m)):
        stage = m.get("stage")
        # Newest first: a candidate can re-enter a stage, and the latest entry
        # is the one the badge should count from.
        event = db.candidate_events.find_one(
            {"candidate_id": m["candidate_id"], "to_stage": stage},
            sort=[("at", -1)],
        )
        if not event or not event.get("at"):
            unexplained.append(m)
            continue

        entered_at = event["at"]
        history = m.get("history") or []
        # An event older than the trail it joins would sort wrong and make the
        # array misleading. Leave those; mapped_at is no worse.
        if history and history[-1].get("at") and entered_at < history[-1]["at"]:
            unexplained.append(m)
            continue

        planned.append((m["_id"], stage, entered_at, event.get("from_stage")))

    return planned, unexplained


def apply(collection, planned: list[tuple]) -> int:
    """Append the recovered StageEvent to each planned mapping."""
    updated = 0
    for oid, stage, entered_at, from_stage in planned:
        # actor="system": this entry was reconstructed, not authored by whoever
        # made the original move, and should not be read as their action.
        event = {
            "stage": stage,
            "from_stage": from_stage,
            "decision": "pending",
            "by_employee_id": None,
            "actor": "system",
            "at": entered_at,
        }
        # The filter repeats the "no event for this stage" condition so a
        # concurrent move that just wrote one is not given a second.
        result = collection.update_one(
            {"_id": oid, "history.stage": {"$ne": stage}},
            {"$push": {"history": event}},
        )
        if result.modified_count:
            updated += 1
        else:
            print(f"    skipped {oid} — an event was written while this ran")
    return updated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="apply the change")
    args = ap.parse_args()

    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    mappings = db.candidate_mappings

    print(f"Database: {settings.MONGODB_DB_NAME}\n")

    total = mappings.count_documents({})
    planned, unexplained = plan(db)

    print(f"Mappings                       : {total}")
    print(f"  no event for current stage   : {len(planned) + len(unexplained)}")

    if not planned and not unexplained:
        print("\nNothing to do.")
        client.close()
        return 0

    by_stage = Counter(stage for _, stage, _, _ in planned)
    print(f"  recoverable from events      : {len(planned)}")
    for stage, n in by_stage.most_common():
        print(f"      {str(stage):18s}: {n}")

    if unexplained:
        print(f"  not recoverable, left alone  : {len(unexplained)}")
        for m in unexplained:
            print(f"      {m['_id']}  stage={m.get('stage')!r}")

    if not planned:
        print("\nNothing to write.")
        client.close()
        return 0

    if not args.confirm:
        print(f"\nDRY RUN. Re-run with --confirm to update {len(planned)} mapping(s).")
        client.close()
        return 0

    updated = apply(mappings, planned)
    print(f"\nDone. Updated {updated} mapping(s).")

    remaining = [m for m in mappings.find({}, {"stage": 1, "history": 1}) if _needs_backfill(m)]
    print(f"Still without an event for their stage: {len(remaining)}")
    client.close()

    # Short of the plan means a concurrent move wrote an event mid-run. Nothing
    # is corrupted, but the run was not the one that was reviewed, so exit
    # non-zero rather than let automation read it as a clean pass.
    if updated < len(planned):
        print(f"WARNING: {len(planned) - updated} planned update(s) were skipped. Re-run.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

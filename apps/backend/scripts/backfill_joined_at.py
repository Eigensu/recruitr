"""Record when each currently-joined mapping was moved to Joined.

Usage (from apps/backend):
    python3 scripts/backfill_joined_at.py            # dry run
    python3 scripts/backfill_joined_at.py --confirm  # apply

The staff pipeline board archives a joined card JOINED_ARCHIVE_DAYS after it
was moved to Joined, reading Mapping.joined_at. move_stage sets that on every
move from now on; mappings that joined before the field existed have none, and
stay on the board until this gives them one.

Where the date comes from, best first:
  1. history — the newest StageEvent for `joined` on the mapping itself;
  2. candidate_events — the newest `to_stage: joined` for that candidate and
     position (the permanent log; seeded and migrated rows may only be here);
  3. updated_at — when the row last changed, which for a card sitting in
     Joined is no earlier than the move. Reported separately so it is visible.

Only joined mappings without a joined_at are touched, and only that field is
written, so re-running is a no-op and nothing else on the row changes.

Take a backup first:
    mongodump --uri "$MONGODB_URI" --db <db> --collection candidate_mappings
"""

import argparse
import pathlib
import sys
from collections import Counter
from datetime import datetime

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient  # noqa: E402

from app.core.config import settings  # noqa: E402

JOINED = "joined"

_MISSING = {"stage": JOINED, "$or": [{"joined_at": None}, {"joined_at": {"$exists": False}}]}


def joined_at_for(mapping: dict, logged_at: datetime | None) -> tuple[datetime | None, str]:
    """When `mapping` was moved to Joined, and which source said so.

    `logged_at` is the newest candidate_events entry for this candidate and
    position moving to joined, if any. Pure, so it is tested without a database.
    """
    for event in reversed(mapping.get("history") or []):
        if event.get("stage") == JOINED and event.get("at"):
            return event["at"], "history"
    if logged_at:
        return logged_at, "candidate_events"
    if mapping.get("updated_at"):
        return mapping["updated_at"], "updated_at"
    return None, "none"


def plan(db) -> tuple[list[tuple], list[dict]]:
    """(planned, unexplained): what would be written, and rows with no date at all. Reads only."""
    planned: list[tuple] = []
    unexplained: list[dict] = []
    fields = {"history": 1, "updated_at": 1, "candidate_id": 1, "position_id": 1}
    for m in db.candidate_mappings.find(_MISSING, fields):
        event = db.candidate_events.find_one(
            {
                "candidate_id": m.get("candidate_id"),
                "position_id": m.get("position_id"),
                "to_stage": JOINED,
            },
            sort=[("at", -1)],
        )
        when, source = joined_at_for(m, event.get("at") if event else None)
        if when is None:
            unexplained.append(m)
        else:
            planned.append((m["_id"], when, source))
    return planned, unexplained


def apply(collection, planned: list[tuple]) -> int:
    """Write joined_at on each planned mapping that is still joined and still without one."""
    updated = 0
    for oid, when, _source in planned:
        # The filter repeats the plan's condition: a card moved, or given a
        # joined_at by a move, while this ran is left as the move made it.
        result = collection.update_one({"_id": oid, **_MISSING}, {"$set": {"joined_at": when}})
        if result.modified_count:
            updated += 1
        else:
            print(f"    skipped {oid} — it changed while this ran")
    return updated


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="apply the change")
    args = ap.parse_args()

    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    mappings = db.candidate_mappings

    print(f"Database: {settings.MONGODB_DB_NAME}\n")
    print(f"Joined mappings                : {mappings.count_documents({'stage': JOINED})}")

    planned, unexplained = plan(db)
    print(f"  without joined_at            : {len(planned) + len(unexplained)}")
    if not planned and not unexplained:
        print("\nNothing to do.")
        client.close()
        return 0

    for source, n in Counter(source for _, _, source in planned).most_common():
        print(f"      from {source:20s}: {n}")
    if unexplained:
        print(f"  no date anywhere, left alone : {len(unexplained)}")
        for m in unexplained:
            print(f"      {m['_id']}")

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
    print(f"Joined mappings still without joined_at: {mappings.count_documents(_MISSING)}")
    client.close()

    # Short of the plan means a card moved mid-run. Nothing is wrong with the
    # data, but the run was not the one that was reviewed, so say so.
    if updated < len(planned):
        print(f"WARNING: {len(planned) - updated} planned update(s) were skipped. Re-run.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

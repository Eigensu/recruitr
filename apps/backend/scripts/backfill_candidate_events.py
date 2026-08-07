"""Reconstruct candidate history from the data that still exists.

Usage (from apps/backend):
    python3 scripts/backfill_candidate_events.py            # dry run
    python3 scripts/backfill_candidate_events.py --confirm  # apply

candidate_events is the permanent record behind the candidate profile: which
companies a person was put in front of, and what came of it. It only started
being written when the feature shipped, so every candidate already in the pool
opens with an empty history.

What can be recovered, per candidate:

  - the opening entry, from the candidate document itself (added by a recruiter,
    or arrived through the public form);
  - one `mapped` entry per mapping, from mapped_at;
  - one `stage_moved` entry per entry in that mapping's own stage history.

What cannot: anything about a mapping that was already deleted (unmapping drops
the row), and the exact timing of moves made before mapping history was being
written — those collapse into a single entry at the mapping's updated_at, which
is when the last move actually happened.

Idempotent per event, not per candidate: skipping a candidate outright because
it already had *one* event (e.g. a live "mapped" recorded after this feature
shipped, from ordinary use of the app) would leave that candidate's opening
entry and any earlier moves permanently unreconstructed — the first run would
never come back for it. Instead each event we are about to write is compared
against what that candidate already has, by (kind, position, stage, timestamp)
rather than by exact content — an identical event from a previous run of this
script is skipped; anything genuinely missing still gets inserted.
"""

import argparse
import pathlib
import sys
from collections import defaultdict
from datetime import UTC, datetime

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient  # noqa: E402

from app.config import settings  # noqa: E402

BATCH = 500
SOURCED = "sourced"
# There is only ever one opening entry per candidate, and this script and the
# live app can each reach a slightly different verdict on which of these two
# it is (created vs applied) depending on what has been backfilled so far —
# so presence of either is enough to say the opening entry already exists.
_OPENING_TYPES = ("created", "applied")


def _signature(event: dict) -> tuple:
    """Identifies one specific life-event, not just "this candidate has
    something recorded" — the key a rerun compares against to tell an event it
    already wrote from a real gap still worth filling."""
    kind = event.get("event_type")
    if kind in _OPENING_TYPES:
        return ("opening",)
    return (kind, event.get("position_id"), event.get("to_stage"), event.get("at"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="apply the change")
    args = ap.parse_args()

    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    now = datetime.now(UTC)

    print(f"Database: {settings.MONGODB_DB_NAME}\n")

    candidates = {
        c["_id"]: c
        for c in db.candidates.find(
            {},
            {
                "brand_id": 1,
                "created_at": 1,
                "created_by_id": 1,
                "source": 1,
                "source_channel": 1,
            },
        )
    }

    # Per-candidate signatures already on record, so the loops below only add
    # what is actually missing instead of skipping a candidate wholesale.
    existing: dict = defaultdict(set)
    for e in db.candidate_events.find(
        {}, {"candidate_id": 1, "event_type": 1, "position_id": 1, "to_stage": 1, "at": 1}
    ):
        existing[e["candidate_id"]].add(_signature(e))
    had_some_history = sum(1 for cid in candidates if existing.get(cid))

    print(f"Candidates                 : {len(candidates)}")
    print(f"  with some history already: {had_some_history}")

    employees = {e["_id"]: e.get("name") for e in db.employees.find({}, {"name": 1})}
    positions = {
        p["_id"]: p
        for p in db.positions.find({}, {"code": 1, "role": 1, "client_id": 1, "client_name": 1})
    }

    events: list[dict] = []
    n_opening = n_mapped = n_moved = 0

    for cid, cand in candidates.items():
        if ("opening",) in existing[cid]:
            continue
        owner = cand.get("created_by_id")
        applied = owner is None and (cand.get("source") or "").lower() == "external"
        channel = cand.get("source_channel")
        events.append(
            {
                "brand_id": cand.get("brand_id"),
                "candidate_id": cid,
                "event_type": "applied" if applied else "created",
                "at": cand.get("created_at") or now,
                "employee_id": owner,
                "employee_name": employees.get(owner),
                "from_stage": None,
                "to_stage": None,
                "note": (
                    f"Applied through the public form ({channel})"
                    if applied and channel
                    else "Applied through the public form"
                    if applied
                    else "Added to the talent pool"
                ),
            }
        )
        existing[cid].add(("opening",))
        n_opening += 1

    for m in db.candidate_mappings.find({"candidate_id": {"$in": list(candidates)}}):
        cand = candidates.get(m["candidate_id"])
        if cand is None:
            continue
        pos = positions.get(m.get("position_id")) or {}
        base = {
            "brand_id": m.get("brand_id") or cand.get("brand_id"),
            "candidate_id": m["candidate_id"],
            "position_id": m.get("position_id"),
            "position_code": pos.get("code"),
            "position_role": pos.get("role"),
            "client_id": m.get("client_id") or pos.get("client_id"),
            "client_name": pos.get("client_name"),
            "note": None,
        }
        mapped_at = m.get("mapped_at") or cand.get("created_at") or now
        actor = m.get("employee_id")
        cid = m["candidate_id"]
        mapped_event = {
            **base,
            "event_type": "mapped",
            "at": mapped_at,
            "employee_id": actor,
            "employee_name": employees.get(actor),
            "from_stage": None,
            "to_stage": SOURCED,
        }
        sig = _signature(mapped_event)
        if sig not in existing[cid]:
            events.append(mapped_event)
            existing[cid].add(sig)
            n_mapped += 1

        history = [h for h in (m.get("history") or []) if h.get("stage") != SOURCED]
        if history:
            previous = SOURCED
            for entry in sorted(history, key=lambda h: h.get("at") or mapped_at):
                by = entry.get("by_employee_id") or actor
                move_event = {
                    **base,
                    "event_type": "stage_moved",
                    "at": entry.get("at") or mapped_at,
                    "employee_id": by,
                    "employee_name": employees.get(by),
                    "from_stage": previous,
                    "to_stage": entry.get("stage"),
                }
                sig = _signature(move_event)
                if sig not in existing[cid]:
                    events.append(move_event)
                    existing[cid].add(sig)
                    n_moved += 1
                previous = entry.get("stage")
        elif m.get("stage") and m["stage"] != SOURCED:
            # Moves made before mapping history existed. The intermediate steps
            # are gone; record where the candidate ended up, when it last moved.
            move_event = {
                **base,
                "event_type": "stage_moved",
                "at": m.get("updated_at") or mapped_at,
                "employee_id": actor,
                "employee_name": employees.get(actor),
                "from_stage": None,
                "to_stage": m["stage"],
                "note": "Reconstructed — intermediate stages were not recorded",
            }
            sig = _signature(move_event)
            if sig not in existing[cid]:
                events.append(move_event)
                existing[cid].add(sig)
                n_moved += 1

    print(f"\nEvents to write            : {len(events)}")
    print(f"  opening entries          : {n_opening}")
    print(f"  mapped                   : {n_mapped}")
    print(f"  stage moves              : {n_moved}")

    if not args.confirm:
        print(f"\nDRY RUN. Re-run with --confirm to insert {len(events)} event(s).")
        client.close()
        return 0

    written = 0
    for i in range(0, len(events), BATCH):
        written += len(db.candidate_events.insert_many(events[i : i + BATCH]).inserted_ids)
    print(f"\nDone. Inserted {written} event(s).")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

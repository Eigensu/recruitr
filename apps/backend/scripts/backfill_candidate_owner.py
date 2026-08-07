"""Fill in Candidate.created_by_id — the recruiter who added each candidate.

Usage (from apps/backend):
    python3 scripts/backfill_candidate_owner.py            # dry run
    python3 scripts/backfill_candidate_owner.py --confirm  # apply

The field was added with CV ownership: a recruiter may open the CV of a
candidate they sourced, and of anyone unowned, but not of a candidate another
recruiter added. Every document that predates the field is therefore unowned,
i.e. shared with the whole desk — correct as a default, but wrong for the many
candidates whose owner can still be worked out.

Two inferences, best first:

  1. The employee on the candidate's earliest mapping. Whoever first put this
     person forward for a position had their CV in hand.
  2. The employee on the earliest activity log that targets the candidate.
     Weaker, and only reaches back 90 days (activities have a TTL), but it
     covers candidates who were added and never mapped.

Anything neither reaches stays null and stays shared. Public-form applications
are skipped outright: nobody sourced them, so they have no owner to find.

Safe to re-run — it only writes to documents whose created_by_id is still unset.
"""

import argparse
import pathlib
import sys
from collections import defaultdict

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient, UpdateOne  # noqa: E402

from app.config import settings  # noqa: E402

BATCH = 500


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="apply the change")
    args = ap.parse_args()

    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]

    print(f"Database: {settings.MONGODB_DB_NAME}\n")

    total = db.candidates.count_documents({})
    unowned = list(
        db.candidates.find(
            {"created_by_id": None},
            {"_id": 1, "source": 1, "full_name": 1},
        )
    )
    print(f"Candidates          : {total}")
    print(f"  without an owner  : {len(unowned)}")

    if not unowned:
        print("\nNothing to do.")
        client.close()
        return 0

    unowned_ids = [c["_id"] for c in unowned]

    # 1. Earliest mapping per candidate. Walked newest-first so that the last
    #    write for a candidate id is the oldest mapping.
    first_mapper: dict = {}
    for m in db.candidate_mappings.find(
        {"candidate_id": {"$in": unowned_ids}},
        {"candidate_id": 1, "employee_id": 1, "mapped_at": 1},
    ).sort("mapped_at", -1):
        if m.get("employee_id"):
            first_mapper[m["candidate_id"]] = m["employee_id"]

    # 2. Earliest surviving activity log per candidate, same walk. Activities
    #    store the target id as a string, not an ObjectId.
    still_missing = {cid for cid in unowned_ids if cid not in first_mapper}
    first_actor: dict = {}
    if still_missing:
        for a in db.activities.find(
            {"target_entity_id": {"$in": [str(c) for c in still_missing]}},
            {"target_entity_id": 1, "employee_id": 1, "created_at": 1},
        ).sort("created_at", -1):
            if a.get("employee_id"):
                first_actor[a["target_entity_id"]] = a["employee_id"]

    names = {e["_id"]: e.get("name", "?") for e in db.employees.find({}, {"name": 1})}

    ops: list[UpdateOne] = []
    per_employee: dict = defaultdict(int)
    skipped_applicants = 0
    for cand in unowned:
        # Public-form applicants first, before any lookup: the docstring's
        # promise is that nobody sourced them, but the mapper/actor lookups
        # below would happily find the recruiter who *later* mapped one to a
        # position and misattribute the CV to them — someone who acted on the
        # application, not the person who brought it in.
        if (cand.get("source") or "").lower() == "external":
            skipped_applicants += 1
            continue
        owner = first_mapper.get(cand["_id"]) or first_actor.get(str(cand["_id"]))
        if owner is None:
            continue
        # created_by_id: None in the filter, not just at select time: two
        # invocations of this script (or a concurrent one) could otherwise
        # race and overwrite an ownership this same write already assigned.
        ops.append(
            UpdateOne(
                {"_id": cand["_id"], "created_by_id": None},
                {"$set": {"created_by_id": owner}},
            )
        )
        per_employee[owner] += 1

    print(f"  attributable      : {len(ops)}")
    print(f"  public applicants : {skipped_applicants} (left unowned by design)")
    print(f"  no signal at all  : {len(unowned) - len(ops) - skipped_applicants}")

    if per_employee:
        print("\nWould assign:")
        for eid, n in sorted(per_employee.items(), key=lambda kv: -kv[1]):
            print(f"    {names.get(eid, str(eid)):40} {n}")

    if not ops:
        print("\nNothing to do.")
        client.close()
        return 0

    if not args.confirm:
        print(f"\nDRY RUN. Re-run with --confirm to update {len(ops)} candidate(s).")
        client.close()
        return 0

    updated = 0
    for i in range(0, len(ops), BATCH):
        updated += db.candidates.bulk_write(ops[i : i + BATCH]).modified_count
    print(f"\nDone. Updated {updated} candidate(s).")
    print(f"Still unowned (shared): {db.candidates.count_documents({'created_by_id': None})}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

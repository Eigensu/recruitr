"""Fill in Mapping.client_id from each mapping's position.

Usage (from apps/backend):
    python3 scripts/backfill_mapping_client_id.py            # dry run
    python3 scripts/backfill_mapping_client_id.py --confirm  # apply

Mapping.client_id is denormalized and was added after the collection already
had data, so older documents have it null. Anything that filters mappings on it
therefore undercounts: the client dashboard and the "filter by client" controls
both quietly omit historical pipeline.

Safe to re-run — it only touches documents whose client_id does not already
match their position's, and derives every value from Position, which has always
carried client_id.
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

    position_client = {
        p["_id"]: p.get("client_id") for p in db.positions.find({}, {"client_id": 1})
    }

    total = db.candidate_mappings.count_documents({})
    missing = db.candidate_mappings.count_documents({"client_id": None})
    print(f"Mappings                     : {total}")
    print(f"  with client_id null/missing: {missing}")

    ops: list[UpdateOne] = []
    orphans = 0
    per_client: dict = defaultdict(int)
    for m in db.candidate_mappings.find({}, {"client_id": 1, "position_id": 1}):
        want = position_client.get(m.get("position_id"))
        if want is None:
            # Position deleted outright — nothing to derive from. Left alone
            # rather than guessed at.
            if m.get("client_id") is None:
                orphans += 1
            continue
        if m.get("client_id") == want:
            continue
        ops.append(UpdateOne({"_id": m["_id"]}, {"$set": {"client_id": want}}))
        per_client[want] += 1

    print(f"  fixable                    : {len(ops)}")
    print(f"  orphaned (position gone)   : {orphans}")

    if per_client:
        names = {c["_id"]: c.get("name", "?") for c in db.clients.find({}, {"name": 1})}
        print("\nWould set client_id on:")
        for cid, n in sorted(per_client.items(), key=lambda kv: -kv[1]):
            print(f"    {names.get(cid, str(cid)):40} {n}")

    if not ops:
        print("\nNothing to do.")
        client.close()
        return 0

    if not args.confirm:
        print(f"\nDRY RUN. Re-run with --confirm to update {len(ops)} mapping(s).")
        client.close()
        return 0

    updated = 0
    for i in range(0, len(ops), BATCH):
        updated += db.candidate_mappings.bulk_write(ops[i : i + BATCH]).modified_count
    print(f"\nDone. Updated {updated} mapping(s).")
    print(
        f"Remaining with null client_id: {db.candidate_mappings.count_documents({'client_id': None})}"
    )
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

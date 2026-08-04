"""READ-ONLY: show every brand and what it owns, so you can decide what is disposable.

Usage (from apps/backend):
    python3 scripts/inspect_brands.py

Touches nothing. Prints one block per brand with per-collection document counts.
"""

import pathlib
import sys

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient  # noqa: E402

from app.config import settings  # noqa: E402

# Every collection that carries brand_id, derived from the Beanie models.
BRAND_SCOPED = [
    "activities",
    "candidate_mappings",
    "candidates",
    "clients",
    "counters",
    "documents",
    "employees",
    "positions",
    "recruiter_tags",
    "recruiters",
    "teams",
]


def main() -> int:
    uri = settings.MONGODB_URI
    where = "ATLAS (production)" if "mongodb+srv" in uri else uri
    print(f"cluster : {where}")
    print(f"database: {settings.MONGODB_DB_NAME}\n")

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[settings.MONGODB_DB_NAME]

    brands = list(db.brands.find({}).sort("created_at", 1))
    if not brands:
        print("No brands found.")
        return 0

    print(f"{len(brands)} brand(s):\n")
    for b in brands:
        bid = b["_id"]
        counts = {c: db[c].count_documents({"brand_id": bid}) for c in BRAND_SCOPED}
        total = sum(counts.values())
        print(f"  {'=' * 70}")
        print(f"  name      : {b.get('name')!r}")
        print(f"  domain    : {b.get('domain')!r}")
        print(f"  _id       : {bid}")
        print(f"  owner_id  : {b.get('owner_id')!r}")
        print(f"  created   : {b.get('created_at')}")
        print(f"  owns      : {total} document(s)")
        for coll, n in counts.items():
            if n:
                print(f"                {coll:22} {n}")
        if total == 0:
            print("                (empty — nothing would be lost)")
        print()

    # Data whose brand_id points at a brand that no longer exists.
    live = {b["_id"] for b in brands}
    print(f"  {'=' * 70}")
    print("  orphans (brand_id pointing at a missing brand):")
    any_orphans = False
    for coll in BRAND_SCOPED:
        n = db[coll].count_documents({"brand_id": {"$nin": list(live)}})
        if n:
            any_orphans = True
            print(f"      {coll:22} {n}")
    if not any_orphans:
        print("      none")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

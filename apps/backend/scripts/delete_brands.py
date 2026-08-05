"""Delete brands and everything scoped to them. Destructive — dry-run by default.

Run inspect_brands.py first and decide which brand ids are disposable.

    # see exactly what would go, change nothing
    python3 scripts/delete_brands.py <brand_id> [<brand_id> ...]

    # write a JSON backup, then delete
    python3 scripts/delete_brands.py <brand_id> --confirm

Deleting only the `brands` row would leave candidates, positions, clients and
mappings behind carrying a dead brand_id — invisible to every query, but still
occupying the (brand_id, email) and (brand_id, code) unique indexes. This
removes the brand and all eleven brand-scoped collections together.

Safety rails:
  - dry-run unless --confirm is passed
  - refuses ids that do not exist
  - refuses to delete every brand (you would lock yourself out)
  - writes a timestamped JSON backup of everything it removes before removing it
"""

import argparse
import datetime as dt
import json
import pathlib
import sys

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from bson import ObjectId  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from app.config import settings  # noqa: E402

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
    ap = argparse.ArgumentParser()
    ap.add_argument("brand_ids", nargs="+", help="brand _id values to delete")
    ap.add_argument("--confirm", action="store_true", help="actually delete")
    args = ap.parse_args()

    try:
        targets = [ObjectId(b) for b in args.brand_ids]
    except Exception as exc:
        print(f"Not a valid ObjectId: {exc}")
        return 1

    uri = settings.MONGODB_URI
    where = "ATLAS (production)" if "mongodb+srv" in uri else uri
    print(f"cluster : {where}")
    print(f"database: {settings.MONGODB_DB_NAME}")
    print(f"mode    : {'DELETE' if args.confirm else 'dry run (nothing will change)'}\n")

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[settings.MONGODB_DB_NAME]

    all_ids = {b["_id"] for b in db.brands.find({}, {"_id": 1})}
    missing = [str(t) for t in targets if t not in all_ids]
    if missing:
        print(f"REFUSING: these brand ids do not exist: {missing}")
        return 1
    if set(targets) >= all_ids:
        print("REFUSING: that would delete every brand, leaving no workspace.")
        return 1

    payload: dict = {"brands": [], "collections": {}}
    grand_total = 0
    for t in targets:
        brand = db.brands.find_one({"_id": t})
        payload["brands"].append(brand)
        print(f"  {brand.get('name')!r}  ({brand.get('domain')})  {t}")
        for coll in BRAND_SCOPED:
            docs = list(db[coll].find({"brand_id": t}))
            if not docs:
                continue
            payload["collections"].setdefault(coll, []).extend(docs)
            grand_total += len(docs)
            print(f"      {coll:22} {len(docs)}")
    print(f"\n  brands: {len(targets)}   related documents: {grand_total}")

    if not args.confirm:
        print("\nDry run. Re-run with --confirm to delete.")
        client.close()
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"brand-delete-backup-{stamp}.json"
    with open(backup, "w") as fh:
        json.dump(payload, fh, indent=2, default=str)
    print(f"\n  backup written: {backup}")

    for coll in BRAND_SCOPED:
        res = db[coll].delete_many({"brand_id": {"$in": targets}})
        if res.deleted_count:
            print(f"      deleted {res.deleted_count:5} from {coll}")
    res = db.brands.delete_many({"_id": {"$in": targets}})
    print(f"      deleted {res.deleted_count:5} from brands")

    remaining = db.brands.count_documents({})
    print(f"\n  done. brands remaining: {remaining}")
    if remaining == 1:
        only = db.brands.find_one({})
        print(f"  single brand left ({only.get('name')!r}) — bare /form will now resolve it.")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

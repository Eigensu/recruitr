"""Repair index option drift that forces init_beanie into skip_indexes=True.

Usage:
    python3 scripts/fix_index_conflicts.py            # dry run, changes nothing
    python3 scripts/fix_index_conflicts.py --confirm  # apply

MongoDB will not change an existing index's options via createIndex — if a
model redefines an index that already exists (same name, different unique /
partialFilterExpression / sparse / TTL / key spec), creation fails with
IndexOptionsConflict (85) or IndexKeySpecsConflict (86). That single failure
makes the app fall back to skip_indexes=True, which disables index sync for
every model, not just the one that conflicted (see app/database.py).

Unlike fix_ttl_indexes.py (which only compares expireAfterSeconds), this
compares the full set of index-defining options, so it also catches cases
like a unique index gaining a partialFilterExpression (e.g. Candidate.email
becoming optional) that the TTL-only script doesn't detect.

This always drops and recreates (no in-place collMod path) since option
changes beyond TTL generally aren't collMod-able. For a unique index there is
a brief window with no uniqueness constraint enforced — acceptable for a
one-off repair, called out here so it isn't run blindly during peak traffic.
"""

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient  # noqa: E402

from app.config import settings  # noqa: E402

# Option keys that define an index's behavior (as opposed to bookkeeping
# fields like 'v' or 'ns' that Mongo adds to the live listing).
COMPARABLE_KEYS = ["unique", "sparse", "partialFilterExpression", "expireAfterSeconds"]


def declared_indexes() -> list[tuple[str, dict]]:
    """(collection, index document) for every index declared on a Beanie model."""
    from beanie import Document

    from app.database import init_db  # noqa: F401  (ensures model modules import)

    def walk(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from walk(sub)

    out = []
    for model in walk(Document):
        st = getattr(model, "Settings", None)
        coll = getattr(st, "name", None)
        for im in getattr(st, "indexes", None) or []:
            if coll:
                out.append((coll, im.document))
    return out


def diff(live: dict, want: dict) -> dict:
    changed = {}
    for key in COMPARABLE_KEYS:
        have, need = live.get(key), want.get(key)
        if have != need:
            changed[key] = (have, need)
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="apply the changes")
    args = ap.parse_args()

    uri = settings.MONGODB_URI
    print(f"cluster : {'ATLAS (production)' if 'mongodb+srv' in uri else uri}")
    print(f"database: {settings.MONGODB_DB_NAME}")
    print(f"mode    : {'APPLY' if args.confirm else 'dry run (nothing will change)'}\n")

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[settings.MONGODB_DB_NAME]

    todo = []
    for coll, want in declared_indexes():
        if coll not in db.list_collection_names():
            continue
        live = {i["name"]: i for i in db[coll].list_indexes()}
        name = want.get("name")
        if name not in live:
            print(f"  {coll}.{name}: absent — init_beanie will create it on next boot")
            continue
        changed = diff(live[name], want)
        if not changed:
            print(f"  {coll}.{name}: already correct")
            continue
        print(f"  {coll}.{name}: option drift")
        for key, (have, need) in changed.items():
            print(f"      {key}: {have!r} -> {need!r}")
        todo.append((coll, want))

    if not todo:
        print("\nNothing to repair.")
        client.close()
        return 0

    if not args.confirm:
        print("\nDry run. Re-run with --confirm to apply.")
        client.close()
        return 0

    print()
    for coll, want in todo:
        name = want["name"]
        key = list(want["key"].items())
        kwargs = {k: want[k] for k in COMPARABLE_KEYS if k in want}
        db[coll].drop_index(name)
        db[coll].create_index(key, name=name, **kwargs)
        print(f"  recreated {coll}.{name}")

    print("\nVerifying:")
    ok = True
    for coll, want in todo:
        name = want["name"]
        live = {i["name"]: i for i in db[coll].list_indexes()}
        changed = diff(live.get(name, {}), want)
        good = name in live and not changed
        ok = ok and good
        print(f"  {'OK  ' if good else 'FAIL'} {coll}.{name}")

    print("\nRestart the backend; init_beanie should now sync indexes without falling back.")
    client.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Repair TTL index drift that forces init_beanie into skip_indexes=True.

Usage:
    python3 scripts/fix_ttl_indexes.py            # dry run, changes nothing
    python3 scripts/fix_ttl_indexes.py --confirm  # apply

MongoDB will not change an existing index's options via createIndex, so a
model that adds expireAfterSeconds to an index that already exists fails with
IndexOptionsConflict (code 85). That single failure makes the app fall back to
skip_indexes=True, which disables index sync for every model.

On MongoDB 5.0+ collMod converts a non-TTL single-field index into a TTL index
in place — no drop, so there is never a window without the index. Older servers
fall back to drop-and-recreate.

WARNING: enabling a TTL starts expiring documents older than the window within
about a minute. This prints the affected count and refuses to proceed without
--confirm.
"""

import argparse
import pathlib
import sys

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import datetime as dt  # noqa: E402

from pymongo import MongoClient  # noqa: E402

from app.config import settings  # noqa: E402


def declared_ttl_indexes() -> list[tuple[str, str, str, int]]:
    """(collection, index_name, field, expireAfterSeconds) declared by the models."""
    from beanie import Document

    from app.database import init_db  # noqa: F401  (imports every model module)

    def walk(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from walk(sub)

    out = []
    for model in walk(Document):
        st = getattr(model, "Settings", None)
        coll = getattr(st, "name", None)
        for im in getattr(st, "indexes", None) or []:
            doc = im.document
            ttl = doc.get("expireAfterSeconds")
            if coll and ttl is not None:
                field = list(dict(doc["key"]).keys())[0]
                out.append((coll, doc["name"], field, ttl))
    return out


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
    major = int(client.server_info()["version"].split(".")[0])
    use_collmod = major >= 5
    print(
        f"server {client.server_info()['version']} -> "
        f"{'collMod (in place)' if use_collmod else 'drop + recreate'}\n"
    )

    todo = []
    for coll, name, field, want in declared_ttl_indexes():
        if coll not in db.list_collection_names():
            continue
        live = {i["name"]: i for i in db[coll].list_indexes()}
        if name not in live:
            print(f"  {coll}.{name}: absent — init_beanie will create it on next boot")
            continue
        have = live[name].get("expireAfterSeconds")
        if have == want:
            print(f"  {coll}.{name}: already correct (TTL {want}s)")
            continue
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=want)
        doomed = db[coll].count_documents({field: {"$lt": cutoff}})
        print(f"  {coll}.{name}: TTL {have} -> {want}")
        print(
            f"      documents older than the window: {doomed}"
            f"{'  <-- these will be deleted' if doomed else ''}"
        )
        todo.append((coll, name, field, want))

    if not todo:
        print("\nNothing to repair.")
        client.close()
        return 0

    if not args.confirm:
        print("\nDry run. Re-run with --confirm to apply.")
        client.close()
        return 0

    print()
    for coll, name, field, want in todo:
        if use_collmod:
            db.command({"collMod": coll, "index": {"name": name, "expireAfterSeconds": want}})
            print(f"  collMod  {coll}.{name} -> TTL {want}s")
        else:
            db[coll].drop_index(name)
            db[coll].create_index([(field, 1)], name=name, expireAfterSeconds=want)
            print(f"  recreated {coll}.{name} -> TTL {want}s")

    print("\nVerifying:")
    ok = True
    for coll, name, _field, want in todo:
        live = {i["name"]: i for i in db[coll].list_indexes()}
        got = live.get(name, {}).get("expireAfterSeconds")
        good = got == want
        ok = ok and good
        print(f"  {'OK  ' if good else 'FAIL'} {coll}.{name}: expireAfterSeconds={got}")

    print("\nRestart the backend; init_beanie should now sync indexes without falling back.")
    client.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

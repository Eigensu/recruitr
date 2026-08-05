"""READ-ONLY: compare the indexes the models declare against what the database has.

Usage:
    python3 scripts/inspect_indexes.py

Highlights TTL mismatches (the IndexOptionsConflict / code 85 that forces
init_beanie into skip_indexes=True) and any declared index that is missing
because that fallback has been suppressing index creation.
"""

import pathlib
import sys

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient  # noqa: E402

from app.config import settings  # noqa: E402


def declared_indexes() -> dict[str, list]:
    """Collection name -> IndexModel list, straight from the Beanie models."""
    from beanie import Document

    from app.database import init_db  # noqa: F401  (ensures model modules import)

    def walk(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from walk(sub)

    out: dict[str, list] = {}
    for model in walk(Document):
        settings_cls = getattr(model, "Settings", None)
        name = getattr(settings_cls, "name", None)
        idx = getattr(settings_cls, "indexes", None)
        if name and idx:
            out[name] = idx
    return out


def main() -> int:
    uri = settings.MONGODB_URI
    print(f"cluster : {'ATLAS (production)' if 'mongodb+srv' in uri else uri}")
    print(f"database: {settings.MONGODB_DB_NAME}\n")

    db = MongoClient(uri, serverSelectionTimeoutMS=10000)[settings.MONGODB_DB_NAME]
    declared = declared_indexes()

    conflicts, missing = [], []
    for coll, models in sorted(declared.items()):
        if coll not in db.list_collection_names():
            continue
        live = {i["name"]: i for i in db[coll].list_indexes()}

        for im in models:
            doc = im.document
            name = doc.get("name")
            want_ttl = doc.get("expireAfterSeconds")
            if name not in live:
                missing.append((coll, name, want_ttl))
                continue
            have_ttl = live[name].get("expireAfterSeconds")
            if want_ttl != have_ttl:
                conflicts.append((coll, name, have_ttl, want_ttl))

    print("TTL / option conflicts (these cause code 85 at startup):")
    if conflicts:
        for coll, name, have, want in conflicts:
            print(f"   {coll}.{name}")
            print(f"       in database : expireAfterSeconds={have}")
            print(f"       models want : expireAfterSeconds={want}")
    else:
        print("   none")

    print("\nDeclared but absent (suppressed by skip_indexes fallback):")
    if missing:
        for coll, name, ttl in missing:
            extra = f"  (TTL {ttl}s)" if ttl else ""
            print(f"   {coll}.{name}{extra}")
    else:
        print("   none")

    print(f"\n{len(conflicts)} conflict(s), {len(missing)} missing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

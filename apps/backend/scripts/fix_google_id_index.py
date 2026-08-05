"""Repair the users.google_id index so email/password signup stops failing.

Usage (from apps/backend):
    python3 scripts/fix_google_id_index.py            # dry run, changes nothing
    python3 scripts/fix_google_id_index.py --confirm  # apply

The index was declared unique + sparse. Sparse only skips documents where the
field is ABSENT, but Beanie serialises every model field, so each password-only
account writes an explicit `google_id: null`. The first such account claims the
null key and every signup after it dies with:

    E11000 duplicate key error ... index: google_id_1 dup key: { google_id: null }

The model now declares a partial index over `{"google_id": {"$type": "string"}}`
instead, which indexes real Google IDs and ignores nulls entirely. MongoDB will
not convert options in place, so the old index has to be dropped and rebuilt —
and until that happens init_beanie hits IndexOptionsConflict (code 85) and
falls back to skip_indexes=True, disabling index sync for EVERY model.

The users collection is small, so the rebuild is near-instant. The window
without a unique index is the duration of one createIndex call.
"""

import argparse
import pathlib
import sys

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient  # noqa: E402
from pymongo.errors import DuplicateKeyError, OperationFailure  # noqa: E402

from app.config import settings  # noqa: E402

INDEX_NAME = "google_id_1"
WANTED = {"google_id": {"$type": "string"}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="apply the change")
    args = ap.parse_args()

    client = MongoClient(settings.MONGODB_URI)
    users = client[settings.MONGODB_DB_NAME]["users"]

    print(f"Database   : {settings.MONGODB_DB_NAME}")
    print("Collection : users\n")

    info = users.index_information()
    current = info.get(INDEX_NAME)
    if current is None:
        print(f"No {INDEX_NAME} index exists — nothing to repair.")
        print("init_beanie will create the partial index on next startup.")
        client.close()
        return 0

    opts = {k: v for k, v in current.items() if k != "v"}
    print(f"Current    : {opts}")
    if current.get("partialFilterExpression") == WANTED:
        print("\nAlready the partial index the model declares. Nothing to do.")
        client.close()
        return 0

    explicit_nulls = users.count_documents({"google_id": {"$type": "null"}})
    real_ids = users.count_documents({"google_id": {"$type": "string"}})
    distinct_ids = len(users.distinct("google_id", {"google_id": {"$type": "string"}}))
    absent = users.count_documents({"google_id": {"$exists": False}})
    print(f"\nAccounts with a real Google ID : {real_ids} ({distinct_ids} distinct)")
    print(f"Accounts with an explicit null : {explicit_nulls}")
    print(f"Accounts with the field absent : {absent}")

    if real_ids != distinct_ids:
        print(
            "\nREFUSING: duplicate Google IDs exist, so the unique index cannot be "
            "rebuilt. Resolve the duplicates first."
        )
        client.close()
        return 1

    if not args.confirm:
        print(
            f"\nDRY RUN. Would drop {INDEX_NAME} and recreate it as unique over "
            f"{WANTED}.\nRe-run with --confirm to apply."
        )
        client.close()
        return 0

    print(f"\nDropping {INDEX_NAME} ...")
    users.drop_index(INDEX_NAME)
    print("Creating partial unique index ...")
    try:
        users.create_index(
            "google_id",
            name=INDEX_NAME,
            unique=True,
            partialFilterExpression=WANTED,
        )
    except (DuplicateKeyError, OperationFailure) as exc:
        print(f"\nFAILED to create the new index: {exc}")
        print("Recreating the previous sparse index so the collection is not left bare.")
        users.create_index("google_id", name=INDEX_NAME, unique=True, sparse=True)
        client.close()
        return 1

    rebuilt = {k: v for k, v in users.index_information()[INDEX_NAME].items() if k != "v"}
    print(f"\nDone. Now: {rebuilt}")
    print("Email/password signup works again, and index sync is no longer blocked.")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Give every referee provisioned before connect codes existed one.

Usage (from apps/backend):
    python3 scripts/backfill_connect_codes.py            # dry run
    python3 scripts/backfill_connect_codes.py --confirm  # apply

RefereeUser.connect_code arrived with the referee portal. Rows written before it
have no code, and until they get one the portal shows a blank code and no
application can be attributed back to the referee.

The API mints a code for such a row on its owner's next sign-in
(utils/connect_code.py), so this script is a convenience, not a prerequisite: it
fills in referees who have not logged in recently, and reports any duplicate
codes, which the unique index on the collection would otherwise refuse to build.

Safe to re-run — it only writes to documents that still have no code.
"""

import argparse
import pathlib
import sys
from collections import Counter

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.modules.recruitment.utils.connect_code import generate_connect_code  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="apply the change")
    args = ap.parse_args()

    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    referees = db.referee_users

    print(f"Database: {settings.MONGODB_DB_NAME}\n")

    total = referees.count_documents({})
    # $type catches the legacy rows (field absent) and any row left with an
    # explicit null, which is just as unusable.
    missing = list(
        referees.find(
            {"connect_code": {"$not": {"$type": "string"}}},
            {"_id": 1, "email": 1},
        )
    )
    print(f"Referees            : {total}")
    print(f"  without a code    : {len(missing)}")

    taken = Counter(
        doc["connect_code"]
        for doc in referees.find({"connect_code": {"$type": "string"}}, {"connect_code": 1})
    )
    duplicates = {code: n for code, n in taken.items() if n > 1}
    if duplicates:
        # Reported rather than repaired: reassigning a code already in
        # circulation would silently break links referees have handed out.
        print(f"  duplicate codes   : {len(duplicates)} — {', '.join(sorted(duplicates))}")
        print("    Resolve these by hand; the unique index cannot build while they exist.")

    if not missing:
        print("\nNothing to do.")
        client.close()
        return 0

    assignments: list[tuple] = []
    for referee in missing:
        code = generate_connect_code()
        while code in taken:
            code = generate_connect_code()
        taken[code] += 1
        assignments.append((referee["_id"], referee.get("email", "?"), code))

    print("\nWould assign:")
    for _, email, code in assignments:
        print(f"    {email:40} {code}")

    if not args.confirm:
        print(f"\nDRY RUN. Re-run with --confirm to update {len(assignments)} referee(s).")
        client.close()
        return 0

    updated = 0
    for oid, email, code in assignments:
        # The filter repeats the "no code" condition so a concurrent sign-in
        # that already minted one is not overwritten with a second code.
        result = referees.update_one(
            {"_id": oid, "connect_code": {"$not": {"$type": "string"}}},
            {"$set": {"connect_code": code}},
        )
        if result.modified_count:
            updated += 1
        else:
            print(f"    skipped {email} — a code was assigned while this ran")

    print(f"\nDone. Updated {updated} referee(s).")
    still_missing = referees.count_documents({"connect_code": {"$not": {"$type": "string"}}})
    print(f"Still without a code: {still_missing}")
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

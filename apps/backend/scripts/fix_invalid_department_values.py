"""One-off fix: clear `department` values that don't match the new Department
enum (PR #48 retyped a free-text field to a strict BOH/Service/Corporate enum
without migrating data), so records stop failing to load.

This does NOT attempt to guess which bucket old free-text values like
"F&B - Kitchen" or "Bar & Beverages" belong in — that's a business call that
needs the actual BOH/Service/Corporate mapping (the PDF spec references an
Excel file for this), not a script's guess. It only clears values that can't
possibly be valid, restoring read access; proper recategorization should be a
follow-up once someone with that mapping does it deliberately.

Touches:
    candidates.department
    positions.department

Idempotent: only ever touches values outside {BOH, Service, Corporate, null}.

Usage:
    python -m scripts.fix_invalid_department_values --dry-run   # report only
    python -m scripts.fix_invalid_department_values             # apply

Take a backup first:
    mongodump --uri "$MONGODB_URI" --db <db> --collection candidates
    mongodump --uri "$MONGODB_URI" --db <db> --collection positions
"""

from __future__ import annotations

import argparse
import asyncio

from pymongo import AsyncMongoClient

from app.config import settings

_VALID = ["BOH", "Service", "Corporate"]


async def _fix(dry_run: bool) -> None:
    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]

    invalid_match = {"department": {"$nin": [*_VALID, None]}}

    for coll_name in ("candidates", "positions"):
        coll = db[coll_name]
        bad_values = await coll.distinct("department", invalid_match)
        count = await coll.count_documents(invalid_match)
        print(f"\n{coll_name}.department: {count} documents with an invalid value")
        for v in sorted(bad_values, key=str):
            n = await coll.count_documents({"department": v})
            print(f"    {v!r}: {n}")
        if not dry_run and count:
            result = await coll.update_many(invalid_match, {"$set": {"department": None}})
            print(f"  -> cleared {result.modified_count} documents")

    mode = "DRY-RUN (no writes)" if dry_run else "APPLIED"
    print(f"\n{'=' * 50}\n department fix — {mode}\n{'=' * 50}")

    if not dry_run:
        remaining = sum(
            [
                await db.candidates.count_documents(invalid_match),
                await db.positions.count_documents(invalid_match),
            ]
        )
        print(f"Remaining invalid department values (should be 0): {remaining}")

    await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()
    asyncio.run(_fix(dry_run=args.dry_run))

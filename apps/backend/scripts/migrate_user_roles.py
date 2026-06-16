"""One-time migration + manual role assignment for the User.role field.

Background: the User model replaced the boolean `is_admin` flag with a
`role` enum (employee | maintainer | admin). This script:

  1. (migrate) Converts every existing user document:
       - is_admin == True            → role = "admin"
       - otherwise / missing role    → role = "employee"
     then removes the obsolete `is_admin` field.

  2. (promote) Manually sets a user's role by email. Role assignment is
     intentionally manual — there is no self-serve UI — so use this to make
     yourself an admin or to appoint a maintainer (CEO) account.

Usage:
    cd apps/backend

    # 1. Run the one-time migration (safe to re-run; idempotent)
    python -m scripts.migrate_user_roles migrate

    # 2. Promote a specific account
    python -m scripts.migrate_user_roles promote --email you@example.com --role admin
    python -m scripts.migrate_user_roles promote --email ceo@example.com --role maintainer

    # List users and their roles
    python -m scripts.migrate_user_roles list
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from pymongo import AsyncMongoClient

from app.config import settings

_VALID_ROLES = {"employee", "maintainer", "admin"}


async def _migrate(db) -> None:
    users = db["users"]

    # Existing admins → role "admin"
    admins = await users.update_many(
        {"is_admin": True},
        {"$set": {"role": "admin", "updated_at": datetime.now(UTC)}},
    )

    # Everyone without a role yet → "employee"
    employees = await users.update_many(
        {"role": {"$exists": False}},
        {"$set": {"role": "employee", "updated_at": datetime.now(UTC)}},
    )

    # Drop the obsolete flag
    dropped = await users.update_many({"is_admin": {"$exists": True}}, {"$unset": {"is_admin": ""}})

    print(f"✓ Promoted {admins.modified_count} admin(s) from is_admin=True")
    print(f"✓ Defaulted {employees.modified_count} user(s) to role=employee")
    print(f"✓ Removed is_admin from {dropped.modified_count} document(s)")


async def _promote(db, email: str, role: str) -> None:
    if role not in _VALID_ROLES:
        print(f"✗ Invalid role '{role}'. Choose one of: {', '.join(sorted(_VALID_ROLES))}")
        return

    result = await db["users"].update_one(
        {"email": email.lower()},
        {"$set": {"role": role, "updated_at": datetime.now(UTC)}},
    )
    if result.matched_count == 0:
        print(f"✗ No user found with email '{email.lower()}'")
    else:
        print(f"✓ Set role='{role}' for '{email.lower()}'")


async def _list(db) -> None:
    users = await db["users"].find({}).to_list(length=None)
    print(f"\nUsers ({len(users)}):")
    for user in users:
        role = user.get("role", user.get("is_admin") and "admin (legacy)" or "—")
        print(f"  {user['email']:<40}  role={role}")


async def run(args: argparse.Namespace, *, mongo_uri: str, db_name: str) -> None:
    client = AsyncMongoClient(mongo_uri)
    db = client[db_name]
    try:
        if args.command == "migrate":
            await _migrate(db)
        elif args.command == "promote":
            await _promote(db, args.email, args.role)
        elif args.command == "list":
            await _list(db)
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate / assign User roles.")
    parser.add_argument("--uri", help="MongoDB connection URI (overrides .env)")
    parser.add_argument("--db", help="MongoDB database name (overrides .env)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="One-time is_admin → role migration")

    promote = sub.add_parser("promote", help="Set a user's role by email")
    promote.add_argument("--email", required=True, help="User login email")
    promote.add_argument(
        "--role", required=True, choices=sorted(_VALID_ROLES), help="Role to assign"
    )

    sub.add_parser("list", help="List users and their roles")

    args = parser.parse_args()
    uri = args.uri or settings.MONGODB_URI
    db = args.db or settings.MONGODB_DB_NAME
    asyncio.run(run(args, mongo_uri=uri, db_name=db))


if __name__ == "__main__":
    main()

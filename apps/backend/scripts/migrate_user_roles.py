"""One-time migration + manual role assignment for the User.role field.

Background: the User model replaced the boolean `is_admin` flag with a
`role` enum (employee | maintainer | admin). This script:

  1. (migrate) Converts every existing user document:
       - is_admin == True            → role = "admin"
       - otherwise / missing role    → role = "employee"
     then removes the obsolete `is_admin` field.

  2. (sync-employee-roles) Copies User.role → Employee.role for every
     employee whose linked user has a non-employee role. Idempotent.
     Run this once after deploying the Employee.role field addition.

  3. (promote) Manually sets a user's role by email. Role assignment is
     intentionally manual — there is no self-serve UI — so use this to make
     yourself an admin or to appoint a maintainer (CEO) account.

Usage:
    cd apps/backend

    # 1. Run the one-time migration (safe to re-run; idempotent)
    python -m scripts.migrate_user_roles migrate

    # 2. Backfill Employee.role from User.role (run once after deploy)
    python -m scripts.migrate_user_roles sync-employee-roles

    # 3. Promote a specific account
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


async def _sync_employee_roles(db) -> None:
    """Copy User.role → Employee.role for every employee, joined by email."""
    users = await db["users"].find({"role": {"$in": ["admin", "maintainer"]}}).to_list(length=None)

    updated = 0
    for user in users:
        result = await db["employees"].update_many(
            {"email": user["email"]},
            {"$set": {"role": user["role"], "updated_at": datetime.now(UTC)}},
        )
        updated += result.modified_count

    # Default everyone else to "employee" if role field is missing
    defaulted = await db["employees"].update_many(
        {"role": {"$exists": False}},
        {"$set": {"role": "employee", "updated_at": datetime.now(UTC)}},
    )

    print(f"✓ Synced {updated} admin/maintainer employee(s)")
    print(f"✓ Defaulted {defaulted.modified_count} employee(s) to role=employee")


async def _list(db) -> None:
    users = await db["users"].find({}).to_list(length=None)
    print(f"\nUsers ({len(users)}):")
    for user in users:
        role = user.get("role") or ("admin (legacy)" if user.get("is_admin") else "—")
        print(f"  {user['email']:<40}  role={role}")


async def run(args: argparse.Namespace, *, mongo_uri: str, db_name: str) -> None:
    client = AsyncMongoClient(mongo_uri)
    db = client[db_name]
    try:
        if args.command == "migrate":
            await _migrate(db)
        elif args.command == "sync-employee-roles":
            await _sync_employee_roles(db)
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
    sub.add_parser(
        "sync-employee-roles", help="Backfill Employee.role from User.role (run once after deploy)"
    )

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

"""Dev utility: assign the demo brand to a login account's employee record.

When you log in with your own Google/email account, ensure_employee_for_user
creates an Employee with brand_id=None. Until brand_id is set, get_tenant()
returns 403 and every API call fails.

This script finds your Employee by email and assigns it to the demo brand
so you can test the full API immediately without completing the onboarding flow.

Usage:
    cd apps/backend
    python -m scripts.dev_assign_brand --email work.eigensu@gmail.com

    # Or: list all employees to find the right one
    python -m scripts.dev_assign_brand --list
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime

from bson import ObjectId
from pymongo import AsyncMongoClient

from app.config import settings


async def run(email: str | None, *, list_mode: bool, mongo_uri: str, db_name: str) -> None:
    client = AsyncMongoClient(mongo_uri)
    db = client[db_name]

    # Find the demo brand
    brand = await db["brands"].find_one({"name": "Binge Consulting"})
    if not brand:
        print("✗ Demo brand not found. Run the seed first:")
        print("    python specs/data/seed.py")
        await client.close()
        return

    if list_mode:
        employees = await db["employees"].find({}).to_list(length=None)
        print(f"\nEmployees ({len(employees)}):")
        for emp in employees:
            bid = str(emp.get("brand_id", "null"))
            uid = str(emp.get("user_id", "null"))
            print(f"  {emp['email']:<40}  brand={bid[:8]}…  user={uid[:8]}…")
        await client.close()
        return

    if not email:
        print("✗ Provide --email or use --list")
        await client.close()
        return

    email_lower = email.lower()
    emp = await db["employees"].find_one({"email": email_lower})
    if not emp:
        # Check if user exists
        user = await db["users"].find_one({"email": email_lower})
        if not user:
            print(f"User '{email_lower}' not found. Creating user document...")
            user_id = ObjectId()
            await db["users"].insert_one(
                {
                    "_id": user_id,
                    "email": email_lower,
                    "full_name": email_lower.split("@")[0].title(),
                    "is_active": True,
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                }
            )
        else:
            user_id = user["_id"]

        print(f"Creating employee record for '{email_lower}'...")
        emp_id = ObjectId()
        await db["employees"].insert_one(
            {
                "_id": emp_id,
                "brand_id": brand["_id"],
                "user_id": user_id,
                "name": email_lower.split("@")[0].title(),
                "email": email_lower,
                "is_active": True,
                "created_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        )
        print(f"✓ Created employee and assigned brand '{brand['name']}' to '{email_lower}'.")
    else:
        await db["employees"].update_one(
            {"_id": emp["_id"]},
            {"$set": {"brand_id": brand["_id"], "updated_at": datetime.now(UTC)}},
        )
        print(f"✓ Assigned brand '{brand['name']}' to employee '{email_lower}'.")

    await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign demo brand to a login account.")
    parser.add_argument("--email", help="Your login email (Google or email/password)")
    parser.add_argument("--list", action="store_true", help="List all employees")
    parser.add_argument("--uri", help="MongoDB connection URI (overrides .env)")
    parser.add_argument("--db", help="MongoDB database name (overrides .env)")
    args = parser.parse_args()

    uri = args.uri or settings.MONGODB_URI
    db = args.db or settings.MONGODB_DB_NAME

    asyncio.run(run(args.email, list_mode=args.list, mongo_uri=uri, db_name=db))


if __name__ == "__main__":
    main()

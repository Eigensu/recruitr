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

from pymongo import AsyncMongoClient

from app.config import settings


async def run(email: str | None, *, list_mode: bool) -> None:
    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]

    # Find the demo brand
    brand = await db["brands"].find_one({"domain": "binge.consulting"})
    if not brand:
        print("✗ Demo brand not found. Run the seed first:")
        print("    python -m app.modules.recruitment.seed")
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

    result = await db["employees"].update_one(
        {"email": email.lower()},
        {"$set": {"brand_id": brand["_id"], "updated_at": datetime.now(UTC)}},
    )

    if result.matched_count == 0:
        print(f"✗ No employee found with email '{email}'.")
        print("  Make sure you have logged in at least once so the employee record is created.")
        print("  Then run this script again.")
    else:
        print(f"✓ Assigned brand '{brand['name']}' to employee '{email}'.")
        print("  You can now log in and use the full API.")

    await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Assign demo brand to a login account.")
    parser.add_argument("--email", help="Your login email (Google or email/password)")
    parser.add_argument("--list", action="store_true", help="List all employees")
    args = parser.parse_args()
    asyncio.run(run(args.email, list_mode=args.list))


if __name__ == "__main__":
    main()

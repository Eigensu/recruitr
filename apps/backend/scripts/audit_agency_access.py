"""READ-ONLY: who can currently read the agency workspace, and who would be refused.

Usage (from apps/backend):
    python3 scripts/audit_agency_access.py

Run this BEFORE setting AGENCY_EMAIL_DOMAINS. It groups every account that
holds a workspace by email domain, so you can see which domains are genuinely
staff — and which accounts got in through the auto-assignment that used to hand
the workspace to anyone who signed up.

Touches nothing.
"""

import pathlib
import sys
from collections import defaultdict

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pymongo import MongoClient  # noqa: E402

from app.config import settings  # noqa: E402


def _domain(email: str) -> str:
    _, _, domain = (email or "").strip().lower().rpartition("@")
    return domain or "(no domain)"


def main() -> int:
    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]

    allowed = settings.agency_email_domains
    print(f"Database : {settings.MONGODB_DB_NAME}")
    print(f"Configured staff domains: {', '.join(sorted(allowed)) or '(none set)'}\n")

    employees = list(db.employees.find({}, {"email": 1, "brand_id": 1, "role": 1, "is_active": 1}))
    users_by_email = {u.get("email", "").lower(): u for u in db.users.find({}, {"email": 1})}

    with_brand: dict[str, list] = defaultdict(list)
    without_brand: dict[str, list] = defaultdict(list)
    for e in employees:
        bucket = with_brand if e.get("brand_id") else without_brand
        bucket[_domain(e.get("email", ""))].append(e)

    print("=" * 72)
    print("HAS WORKSPACE ACCESS  (an Employee row with a brand_id)")
    print("=" * 72)
    for domain in sorted(with_brand, key=lambda d: (-len(with_brand[d]), d)):
        rows = with_brand[domain]
        verdict = "allowed by domain" if domain in allowed else "kept via existing Employee row"
        print(f"\n  @{domain}  — {len(rows)} account(s)  [{verdict}]")
        for e in sorted(rows, key=lambda r: r.get("email", "")):
            email = e.get("email", "")
            flags = []
            if not e.get("is_active", True):
                flags.append("inactive")
            if email.lower() not in users_by_email:
                flags.append("no login user")
            suffix = f"  ({', '.join(flags)})" if flags else ""
            print(f"      {email:45} role={e.get('role', '?'):11}{suffix}")

    if without_brand:
        print("\n" + "=" * 72)
        print("NO WORKSPACE  (blocked today; sees the onboarding screen)")
        print("=" * 72)
        for domain in sorted(without_brand):
            emails = sorted(e.get("email", "") for e in without_brand[domain])
            print(f"\n  @{domain}  — {len(emails)} account(s)")
            for email in emails:
                print(f"      {email}")

    outside = {d: v for d, v in with_brand.items() if d not in allowed}
    print("\n" + "=" * 72)
    total = sum(len(v) for v in with_brand.values())
    print(f"{total} account(s) hold the workspace across {len(with_brand)} domain(s).")
    if not allowed:
        print(
            "\nAGENCY_EMAIL_DOMAINS is not set, so NO new account can be provisioned.\n"
            "Pick the staff domains from the list above and set it, comma-separated."
        )
    elif outside:
        print(
            f"\n{sum(len(v) for v in outside.values())} account(s) on "
            f"{len(outside)} unlisted domain(s) keep access because they already "
            "have an Employee row: " + ", ".join(f"@{d}" for d in sorted(outside)) + "\n"
            "Review them. To revoke one, unset its brand_id on the employees row."
        )
    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Move un-actioned candidates onto the Leads page and hide telecaller rejects, once.

Usage (from apps/backend):
    python3 scripts/migrate_candidates_to_leads.py            # report only, writes nothing
    python3 scripts/migrate_candidates_to_leads.py --confirm  # do it

The Candidates page no longer has an External tab, which was the only place a
PENDING candidate without a lead could be decided. Two things follow:

  1. Every active PENDING candidate with no IntakeLead gets one, queued for a
     telecaller by the same round-robin the public form uses
     (`open_lead_for_application`), or left `unassigned` when the brand has no
     telecaller. PENDING only ever came from the public form and the sheet
     ingest, and the ingest always opens a lead, so these are applicants from
     before the lead flow existed.

  2. Candidates a telecaller already rejected are soft-deleted
     (is_active=False), as a telecaller reject now does going forward. Only
     those whose lead carries a telecaller reject: REJECTED candidates decided
     some other way (the old External tab's reject button) are counted in the
     report and left alone.

Safe to re-run: a candidate that has a lead is skipped in step 1, and step 2
only touches rows that are still active.
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys
from collections import Counter

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.common.utils.seed_guard import assert_local_database  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import init_db  # noqa: E402
from app.modules.recruitment.enums import (  # noqa: E402
    CandidateStatus,
    IntakeDecision,
    IntakeLeadStatus,
)
from app.modules.recruitment.models import Candidate, IntakeLead  # noqa: E402
from app.modules.recruitment.service.intake_service import (  # noqa: E402
    open_lead_for_application,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--confirm", action="store_true", help="actually write (default: report only)"
    )
    return parser.parse_args()


async def _pending_without_lead() -> list[Candidate]:
    pending = await Candidate.find(
        {"status": CandidateStatus.pending.value, "is_active": True}
    ).to_list()
    if not pending:
        return []
    with_lead = set(
        await IntakeLead.get_motor_collection().distinct(
            "candidate_id", {"candidate_id": {"$in": [c.id for c in pending]}}
        )
    )
    return [c for c in pending if c.id not in with_lead]


async def _rejected_still_active() -> tuple[list[Candidate], int]:
    """(telecaller-rejected candidates still active, other REJECTED ones left alone)."""
    rejected = await Candidate.find(
        {"status": CandidateStatus.rejected.value, "is_active": True}
    ).to_list()
    if not rejected:
        return [], 0
    by_telecaller = set(
        await IntakeLead.get_motor_collection().distinct(
            "candidate_id",
            {
                "candidate_id": {"$in": [c.id for c in rejected]},
                "telecaller_decision": IntakeDecision.reject.value,
            },
        )
    )
    hide = [c for c in rejected if c.id in by_telecaller]
    return hide, len(rejected) - len(hide)


async def run(*, confirm: bool) -> dict[str, int]:
    """Report, and with `confirm` apply. Returns the counts, for the tests."""
    orphans = await _pending_without_lead()
    to_hide, left_alone = await _rejected_still_active()

    per_brand = Counter(str(c.brand_id) for c in orphans)
    print("\nPENDING candidates with no lead (→ Leads page)")
    print(f"  total                       {len(orphans):>7,}")
    for brand, count in sorted(per_brand.items()):
        print(f"    brand {brand}  {count:>7,}")
    print("REJECTED candidates still active")
    print(f"  rejected by a telecaller    {len(to_hide):>7,}   ← will be soft-deleted")
    print(f"  rejected some other way     {left_alone:>7,}   ← left as they are")

    counts = {"leads_opened": 0, "unassigned": 0, "hidden": 0, "left_alone": left_alone}
    if not confirm:
        print("\nNothing written. Re-run with --confirm to apply.\n")
        counts |= {"would_open": len(orphans), "would_hide": len(to_hide)}
        return counts

    for candidate in orphans:
        lead = await open_lead_for_application(candidate)
        if lead is None:
            continue  # opened by something else since the report was read
        counts["leads_opened"] += 1
        if lead.status == IntakeLeadStatus.unassigned:
            counts["unassigned"] += 1

    if to_hide:
        result = await Candidate.find(
            {"_id": {"$in": [c.id for c in to_hide]}, "is_active": True}
        ).update({"$set": {"is_active": False}})
        counts["hidden"] = result.modified_count if result is not None else 0

    print(f"\n  leads opened                {counts['leads_opened']:>7,}")
    print(
        f"    of which unassigned       {counts['unassigned']:>7,}   ← no telecaller to take them"
    )
    print(f"  candidates soft-deleted     {counts['hidden']:>7,}\n")
    return counts


async def _main(args: argparse.Namespace) -> None:
    await init_db()
    await run(confirm=args.confirm)


def main() -> None:
    args = _parse_args()
    if args.confirm:
        # The repo-root .env points at the live Atlas cluster. Reporting is
        # read-only and unguarded; writing is not.
        assert_local_database(settings.MONGODB_URI, action="migrate candidates in")
    asyncio.run(_main(args))


if __name__ == "__main__":
    main()

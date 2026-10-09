"""Move un-actioned candidates onto the Leads page and hide telecaller rejects, once.

Usage (from apps/backend):
    python3 scripts/migrate_candidates_to_leads.py                     # report only
    python3 scripts/migrate_candidates_to_leads.py --confirm           # do it
    python3 scripts/migrate_candidates_to_leads.py --confirm --assign  # and queue them

The Candidates page no longer has an External tab, which was the only place a
PENDING candidate without a lead could be decided. Three things follow:

  1. Every active PENDING candidate with no lead of their own gets one. A
     `duplicate` lead pointing at them does not count as theirs: it is a sheet
     row matched to them, not their screening. PENDING only ever came from the
     public form and the sheet ingest, so these are applicants from before the
     lead flow existed, whose lead failed to open, or whose lead was removed
     and whose own row the next ingest then filed as a duplicate of them.

     Someone with a duplicate row has their earliest one queued
     (`screen_duplicate_lead`), keeping the ad that brought them and the date
     they applied. Anyone else gets a new public-form lead
     (`open_lead_for_application`), dated when their candidate was created.
     Either way the analytics file them in the week they arrived rather than
     the week this ran, and the lead is left `unassigned` — a backlog handed
     out at once would start every telecaller's SLA clock together and breach
     them all a day later. --assign round-robins them to telecallers instead;
     otherwise assign from the Leads page.

  2. Candidates a telecaller already rejected are soft-deleted
     (is_active=False), as a telecaller reject now does going forward. Only
     those whose lead carries a telecaller reject: REJECTED candidates decided
     some other way (the old External tab's reject button) are counted in the
     report and left alone.

  3. Candidates whose lead waits in a recruiter's Review tab go back to
     PENDING. The old flow approved them when an admin assigned the team; now
     only the recruiter's Accept does, and until then they belong in the
     Review tab alone.

Safe to re-run: step 1 skips anyone with a lead, step 2 only touches rows that
are still active, and step 3 only rows that are still APPROVED.
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys
from collections import Counter
from datetime import datetime

from beanie import PydanticObjectId

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
    as_utc,
    open_lead_for_application,
    screen_duplicate_lead,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--confirm", action="store_true", help="actually write (default: report only)"
    )
    parser.add_argument(
        "--assign",
        action="store_true",
        help="round-robin the opened leads to telecallers, starting their SLA clocks",
    )
    return parser.parse_args()


async def _pending_without_lead() -> list[Candidate]:
    pending = await Candidate.find(
        {"status": CandidateStatus.pending.value, "is_active": True}
    ).to_list()
    if not pending:
        return []
    with_lead = set(
        await IntakeLead.distinct(
            "candidate_id",
            {
                "candidate_id": {"$in": [c.id for c in pending]},
                "status": {"$ne": IntakeLeadStatus.duplicate.value},
            },
        )
    )
    return [c for c in pending if c.id not in with_lead]


def _applied_at(lead: IntakeLead) -> datetime:
    return as_utc(lead.external_created_at or lead.created_at)  # type: ignore[return-value]


async def _earliest_duplicates(candidates: list[Candidate]) -> dict[PydanticObjectId, IntakeLead]:
    """Each candidate's first `duplicate` lead, for those who have any."""
    if not candidates:
        return {}
    duplicates = await IntakeLead.find(
        {
            "candidate_id": {"$in": [c.id for c in candidates]},
            "status": IntakeLeadStatus.duplicate.value,
        }
    ).to_list()
    earliest: dict[PydanticObjectId, IntakeLead] = {}
    for lead in duplicates:
        current = earliest.get(lead.candidate_id)
        if current is None or _applied_at(lead) < _applied_at(current):
            earliest[lead.candidate_id] = lead
    return earliest


async def _rejected_still_active() -> tuple[list[Candidate], int]:
    """(telecaller-rejected candidates still active, other REJECTED ones left alone)."""
    rejected = await Candidate.find(
        {"status": CandidateStatus.rejected.value, "is_active": True}
    ).to_list()
    if not rejected:
        return [], 0
    by_telecaller = set(
        await IntakeLead.distinct(
            "candidate_id",
            {
                "candidate_id": {"$in": [c.id for c in rejected]},
                "telecaller_decision": IntakeDecision.reject.value,
            },
        )
    )
    hide = [c for c in rejected if c.id in by_telecaller]
    return hide, len(rejected) - len(hide)


async def _approved_in_review() -> list[Candidate]:
    """APPROVED candidates whose lead still waits on a recruiter's decision."""
    in_review = await IntakeLead.distinct(
        "candidate_id",
        {"status": IntakeLeadStatus.pending_recruiter.value, "recruiter_decision": None},
    )
    if not in_review:
        return []
    return await Candidate.find(
        {"_id": {"$in": in_review}, "status": CandidateStatus.approved.value, "is_active": True}
    ).to_list()


async def run(*, confirm: bool, assign: bool = False) -> dict[str, int]:
    """Report, and with `confirm` apply. Returns the counts, for the tests."""
    orphans = await _pending_without_lead()
    their_rows = await _earliest_duplicates(orphans)
    to_screen = list(their_rows.values())
    to_open = [c for c in orphans if c.id not in their_rows]
    to_hide, left_alone = await _rejected_still_active()
    to_unapprove = await _approved_in_review()

    per_brand = Counter(str(c.brand_id) for c in orphans)
    print("\nPENDING candidates with no lead (→ Leads page)")
    print(f"  total                       {len(orphans):>7,}")
    for brand, count in sorted(per_brand.items()):
        print(f"    brand {brand}  {count:>7,}")
    print(f"  their duplicate row queued  {len(to_screen):>7,}   ← keeps the ad and the date")
    print(f"  new public-form lead        {len(to_open):>7,}")
    print("REJECTED candidates still active")
    print(f"  rejected by a telecaller    {len(to_hide):>7,}   ← will be soft-deleted")
    print(f"  rejected some other way     {left_alone:>7,}   ← left as they are")
    print("APPROVED candidates waiting in a recruiter's Review tab")
    print(f"  total                       {len(to_unapprove):>7,}   ← back to PENDING")

    counts = {
        "leads_opened": 0,
        "duplicates_queued": 0,
        "unassigned": 0,
        "hidden": 0,
        "left_alone": left_alone,
        "unapproved": 0,
    }
    if not confirm:
        print("\nNothing written. Re-run with --confirm to apply.\n")
        counts |= {
            "would_open": len(to_open),
            "would_queue_duplicate": len(to_screen),
            "would_hide": len(to_hide),
            "would_unapprove": len(to_unapprove),
        }
        return counts

    for lead in to_screen:
        status = await screen_duplicate_lead(lead, assign=assign)
        if status is None:
            continue  # no longer a duplicate since the report was read
        counts["duplicates_queued"] += 1
        if status == IntakeLeadStatus.unassigned:
            counts["unassigned"] += 1

    for candidate in to_open:
        lead = await open_lead_for_application(
            candidate, assign=assign, arrived_at=candidate.created_at
        )
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

    if to_unapprove:
        result = await Candidate.find(
            {
                "_id": {"$in": [c.id for c in to_unapprove]},
                "status": CandidateStatus.approved.value,
            }
        ).update({"$set": {"status": CandidateStatus.pending.value}})
        counts["unapproved"] = result.modified_count if result is not None else 0

    unassigned_note = (
        "← assign from the Leads page" if not assign else "← no telecaller to take them"
    )
    print(f"\n  leads opened                {counts['leads_opened']:>7,}")
    print(f"  duplicate rows queued       {counts['duplicates_queued']:>7,}")
    print(f"    of which unassigned       {counts['unassigned']:>7,}   {unassigned_note}")
    print(f"  candidates soft-deleted     {counts['hidden']:>7,}")
    print(f"  candidates back to PENDING  {counts['unapproved']:>7,}\n")
    return counts


async def _main(args: argparse.Namespace) -> None:
    await init_db()
    await run(confirm=args.confirm, assign=args.assign)


def main() -> None:
    args = _parse_args()
    if args.confirm:
        # The repo-root .env points at the live Atlas cluster. Reporting is
        # read-only and unguarded; writing is not.
        assert_local_database(settings.MONGODB_URI, action="migrate candidates in")
    asyncio.run(_main(args))


if __name__ == "__main__":
    main()

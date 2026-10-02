"""Import the lead sheet's existing history, deliberately and once.

Usage (from apps/backend):
    python3 scripts/backfill_intake_leads.py                  # report only, writes nothing
    python3 scripts/backfill_intake_leads.py --confirm        # import, assigned to nobody
    python3 scripts/backfill_intake_leads.py --confirm --assign
    python3 scripts/backfill_intake_leads.py --since 2026-06-01 --limit 50 --confirm

The scheduled poll ignores everything that was in the sheet before the
integration was switched on (IntakeSourceConfig.activated_at), so without this
script that history never enters the system at all. Automating it was rejected:
importing a few hundred old leads is a decision with visible consequences for
whoever has to call them, and it should be made on purpose, with the numbers in
front of you.

Report mode is the point of the script. It reads the sheet, compares it against
the database and prints what an import would do — how many of these people you
already have, how many rows are unusable, how much of the sheet is the same
person twice — without writing anything.

Imported leads are left `unassigned` unless --assign is given. Leads months old
would breach their SLA on the next sweep, all at once, burying the admin
dashboard in alerts for work nobody was ever going to do that day. Import,
look at what landed, then assign from the admin UI if the backlog is worth
working.

Safe to re-run: (brand_id, external_id) is unique on IntakeLead, so rows already
imported are skipped.
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import sys
from datetime import UTC, datetime

# Resolve the backend package regardless of where this is invoked from.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.common.utils.seed_guard import assert_local_database  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import init_db  # noqa: E402
from app.modules.recruitment.service.intake_service import (  # noqa: E402
    before_cutoff,
    contact_coverage,
    ingest_leads,
    plan_ingest,
    resolve_source_config,
)
from app.modules.recruitment.utils.google_sheets import (  # noqa: E402
    SheetConfigurationError,
    SheetReadError,
    fetch_values,
)
from app.modules.recruitment.utils.lead_sheet import ParsedLead, parse_rows  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--confirm", action="store_true", help="actually import (default: report only)"
    )
    parser.add_argument("--since", metavar="YYYY-MM-DD", help="only rows created on or after this")
    parser.add_argument(
        "--assign",
        action="store_true",
        help="round-robin the imported leads to telecallers, starting their SLA clocks",
    )
    parser.add_argument("--limit", type=int, help="import at most this many rows")
    return parser.parse_args()


def _since(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        raise SystemExit(f"--since must be YYYY-MM-DD, not {value!r}") from None


def _date_range(leads: list[ParsedLead]) -> str:
    dates = sorted(lead.external_created_at for lead in leads if lead.external_created_at)
    if not dates:
        return "unknown"
    return f"{dates[0]:%Y-%m-%d} … {dates[-1]:%Y-%m-%d}"


async def _run(args: argparse.Namespace) -> None:
    await init_db()

    config = await resolve_source_config()
    if config is None:
        raise SystemExit(
            "No intake source configured. Set INTAKE_SPREADSHEET_ID (and make sure exactly "
            "one brand exists), or create the IntakeSourceConfig row first."
        )

    try:
        values = await fetch_values(config.spreadsheet_id, config.sheet_range)
    except (SheetConfigurationError, SheetReadError) as exc:
        raise SystemExit(f"Could not read the sheet: {exc}") from None

    leads, skipped = parse_rows(
        values,
        default_source_channel=config.default_source_channel,
        overrides=settings.intake_column_overrides,
    )

    cutoff = _since(args.since)
    eligible = [lead for lead in leads if not before_cutoff(lead, cutoff)]
    excluded = len(leads) - len(eligible)
    if args.limit is not None:
        eligible = eligible[: args.limit]

    total, reachable = await contact_coverage(config.brand_id)
    plan = await plan_ingest(eligible, brand_id=config.brand_id)

    print(f"\nBrand: {config.brand_id}")
    print(f"  candidates in system        {total:>7,}")
    print(f"    matchable (phone/email)   {reachable:>7,}   ← dedupe can only see these")
    print(f"  sheet rows read             {max(len(values) - 1, 0):>7,}")
    print(f"    unusable (no name/phone)  {len(skipped):>7,}")
    if args.since:
        print(f"    before --since            {excluded:>7,}")
    print(f"    already ingested          {plan.already_ingested:>7,}")
    print(
        f"    duplicate within sheet    {plan.duplicate_in_sheet:>7,}   ← same person, two lead ids"
    )
    print(f"    match an existing person  {plan.matched_existing:>7,}   ← would link, not create")
    print(f"    genuinely new             {plan.new:>7,}")
    print(f"  date range in sheet         {_date_range(eligible)}")

    if not args.confirm:
        print("\nNothing written. Re-run with --confirm to import.\n")
        return

    destination = "assigned to telecallers" if args.assign else "left unassigned"
    # Every row that is not already ingested becomes a lead, including the ones
    # that link to somebody you already have: two ad clicks were paid for.
    to_import = plan.new + plan.matched_existing + plan.duplicate_in_sheet
    print(f"\nImporting {to_import:,} rows, {destination}…")
    result = await ingest_leads(eligible, brand_id=config.brand_id, assign=args.assign)

    print(f"  created                     {result.created:>7,}")
    print(f"  linked to existing people   {result.matched_existing:>7,}")
    print(f"  already ingested            {result.already_ingested:>7,}")
    print(f"  assigned / waiting          {result.assigned:>7,} / {result.unassigned:,}")
    for error in result.errors:
        print(f"  ! {error}")
    if not args.assign and result.unassigned:
        print("\nImported leads are in nobody's queue. Assign them from the admin UI when ready.")
    print()


def main() -> None:
    args = _parse_args()
    if args.confirm:
        # The repo-root .env points at the live Atlas cluster. Reporting is
        # read-only and unguarded; writing is not.
        assert_local_database(settings.MONGODB_URI, action="import leads into")
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()

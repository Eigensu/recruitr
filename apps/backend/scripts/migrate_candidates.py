"""One-off migration: normalise the `candidates` collection to the unified schema.

Historically two models wrote this collection: the recruiter-world `Candidate`
(`name`) and the dashboard-world `DashboardCandidate` (`full_name`). This script
backfills the canonical fields and removes the legacy ones, then prints a report.

Idempotent: only sets fields when missing. Safe to re-run.

Usage:
    python -m scripts.migrate_candidates            # apply
    python -m scripts.migrate_candidates --dry-run  # report only, no writes

Take a backup first:
    mongodump --uri "$MONGODB_URI" --collection candidates --db <db>
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field

from pymongo import AsyncMongoClient

from app.config import settings


@dataclass
class MigrationReport:
    total: int = 0
    full_name_only: int = 0
    name_only: int = 0
    both_fields: int = 0
    missing_both: int = 0
    source_defaulted: int = 0
    tags_defaulted: int = 0
    skills_backfilled: int = 0
    cv_link_backfilled: int = 0
    migrated: int = 0
    failures: list[str] = field(default_factory=list)

    def render(self, *, dry_run: bool) -> str:
        mode = "DRY-RUN (no writes)" if dry_run else "APPLIED"
        return "\n".join(
            [
                "",
                "=" * 52,
                f" Candidate Migration Report — {mode}",
                "=" * 52,
                f" Total candidates scanned ........ {self.total}",
                f" Candidates with full_name only .. {self.full_name_only}",
                f" Candidates with name only ....... {self.name_only}",
                f" Candidates with both fields ..... {self.both_fields}",
                f" Candidates missing both ......... {self.missing_both}",
                f" Candidates migrated/updated ..... {self.migrated}",
                f" Source defaults assigned ........ {self.source_defaulted}",
                f" Tags defaults assigned .......... {self.tags_defaulted}",
                f" Skills backfilled (skills→…) .... {self.skills_backfilled}",
                f" CV link backfilled (resume_link) {self.cv_link_backfilled}",
                f" Migration failures .............. {len(self.failures)}",
                "=" * 52,
            ]
            + ([" Failure ids:"] + [f"  - {f}" for f in self.failures] if self.failures else [])
        )


async def migrate(*, dry_run: bool) -> MigrationReport:
    report = MigrationReport()
    client = AsyncMongoClient(settings.MONGODB_URI)
    col = client[settings.MONGODB_DB_NAME]["candidates"]

    try:
        cursor = col.find({})
        async for doc in cursor:
            report.total += 1
            doc_id = doc.get("_id")
            try:
                has_name = bool(doc.get("name"))
                has_full = bool(doc.get("full_name"))
                if has_name and has_full:
                    report.both_fields += 1
                elif has_name:
                    report.name_only += 1
                elif has_full:
                    report.full_name_only += 1
                else:
                    report.missing_both += 1

                set_ops: dict = {}
                unset_ops: dict = {}

                if not has_name and has_full:
                    set_ops["name"] = doc["full_name"]
                if not has_name and not has_full:
                    # Last-resort placeholder so the doc is parseable.
                    set_ops["name"] = doc.get("email", "Unnamed Candidate")

                if not doc.get("extracted_skills") and doc.get("skills"):
                    set_ops["extracted_skills"] = doc["skills"]
                    report.skills_backfilled += 1

                if not doc.get("cv_link") and doc.get("resume_link"):
                    set_ops["cv_link"] = doc["resume_link"]
                    report.cv_link_backfilled += 1

                if not doc.get("source"):
                    set_ops["source"] = "internal"
                    report.source_defaulted += 1

                if doc.get("tags") is None:
                    set_ops["tags"] = []
                    report.tags_defaulted += 1

                for legacy in ("full_name", "skills", "resume_link"):
                    if legacy in doc:
                        unset_ops[legacy] = ""

                if set_ops or unset_ops:
                    report.migrated += 1
                    if not dry_run:
                        update: dict = {}
                        if set_ops:
                            update["$set"] = set_ops
                        if unset_ops:
                            update["$unset"] = unset_ops
                        await col.update_one({"_id": doc_id}, update)
            except Exception as exc:  # noqa: BLE001 — record and continue
                report.failures.append(f"{doc_id}: {exc}")
    finally:
        await client.close()

    return report


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Normalise the candidates collection")
    parser.add_argument("--dry-run", action="store_true", help="Report only; do not write")
    args = parser.parse_args()

    report = await migrate(dry_run=args.dry_run)
    print(report.render(dry_run=args.dry_run))


if __name__ == "__main__":
    asyncio.run(_main())

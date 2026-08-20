"""One-off migration: remap PipelineStage values that PR #48 ("Feat/client
positions") renamed, in every collection that stores them.

PR #48 removed decision_pending/offer/offer_accepted/position_close from the
PipelineStage enum in favour of selected/joined, but existing documents still
carry the old strings. Any strict Beanie load (Candidate.find, Mapping.find,
CandidateEvent.find) of a document holding one of those old values raises a
Pydantic ValidationError — which is why the dashboard started returning empty
results / 500s for every candidate/mapping touching one of them.

Mapping applied (old -> new), matching how the new stages are actually used
(see controller/pipeline.py's ClientActionModal-backed endpoints):
    decision_pending -> interview   (still awaiting the post-interview decision)
    offer            -> selected    (selected, offer not yet uploaded)
    offer_accepted   -> selected    (selected; offer_letter_url/joining_date are
                                      now just fields on the `selected` stage)
    position_close   -> joined

Touches:
    candidates.current_stage
    candidate_mappings.stage
    candidate_mappings.history[].stage / history[].from_stage
    candidate_events.from_stage / candidate_events.to_stage

Idempotent: only ever matches the four old values, so re-running after a
partial apply is safe.

Usage:
    python -m scripts.migrate_old_pipeline_stages --dry-run   # report only
    python -m scripts.migrate_old_pipeline_stages             # apply

Take a backup first:
    mongodump --uri "$MONGODB_URI" --db <db> \
        --collection candidates --collection candidate_mappings \
        --collection candidate_events
"""

from __future__ import annotations

import argparse
import asyncio

from pymongo import AsyncMongoClient

from app.config import settings

_STAGE_MAP = {
    "decision_pending": "interview",
    "offer": "selected",
    "offer_accepted": "selected",
    "position_close": "joined",
}
_OLD_VALUES = list(_STAGE_MAP.keys())


async def _migrate(dry_run: bool) -> None:
    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]

    report: dict[str, int] = {}

    # 1. candidates.current_stage
    for old, new in _STAGE_MAP.items():
        count = await db.candidates.count_documents({"current_stage": old})
        report[f"candidates.current_stage {old} -> {new}"] = count
        if not dry_run and count:
            await db.candidates.update_many(
                {"current_stage": old}, {"$set": {"current_stage": new}}
            )

    # 2. candidate_mappings.stage
    for old, new in _STAGE_MAP.items():
        count = await db.candidate_mappings.count_documents({"stage": old})
        report[f"candidate_mappings.stage {old} -> {new}"] = count
        if not dry_run and count:
            await db.candidate_mappings.update_many({"stage": old}, {"$set": {"stage": new}})

    # 3. candidate_mappings.history[].stage / history[].from_stage
    # Array elements can't be $set by value-match alone across every matching
    # element in one call, so update per old value with arrayFilters.
    for old, new in _STAGE_MAP.items():
        count = await db.candidate_mappings.count_documents({"history.stage": old})
        report[f"candidate_mappings.history[].stage {old} -> {new}"] = count
        if not dry_run and count:
            await db.candidate_mappings.update_many(
                {"history.stage": old},
                {"$set": {"history.$[elem].stage": new}},
                array_filters=[{"elem.stage": old}],
            )

        count_from = await db.candidate_mappings.count_documents({"history.from_stage": old})
        report[f"candidate_mappings.history[].from_stage {old} -> {new}"] = count_from
        if not dry_run and count_from:
            await db.candidate_mappings.update_many(
                {"history.from_stage": old},
                {"$set": {"history.$[elem].from_stage": new}},
                array_filters=[{"elem.from_stage": old}],
            )

    # 4. candidate_events.from_stage / to_stage
    for old, new in _STAGE_MAP.items():
        count_from = await db.candidate_events.count_documents({"from_stage": old})
        report[f"candidate_events.from_stage {old} -> {new}"] = count_from
        if not dry_run and count_from:
            await db.candidate_events.update_many(
                {"from_stage": old}, {"$set": {"from_stage": new}}
            )

        count_to = await db.candidate_events.count_documents({"to_stage": old})
        report[f"candidate_events.to_stage {old} -> {new}"] = count_to
        if not dry_run and count_to:
            await db.candidate_events.update_many({"to_stage": old}, {"$set": {"to_stage": new}})

    mode = "DRY-RUN (no writes)" if dry_run else "APPLIED"
    print(f"\n{'=' * 60}\n Pipeline stage rename migration — {mode}\n{'=' * 60}")
    for line, count in report.items():
        marker = " " if count == 0 else "*"
        print(f" {marker} {line}: {count}")
    print(f"{'=' * 60}\n")

    # Verify no old values remain anywhere, when applying.
    if not dry_run:
        remaining = {
            "candidates.current_stage": await db.candidates.count_documents(
                {"current_stage": {"$in": _OLD_VALUES}}
            ),
            "candidate_mappings.stage": await db.candidate_mappings.count_documents(
                {"stage": {"$in": _OLD_VALUES}}
            ),
            "candidate_mappings.history.stage": await db.candidate_mappings.count_documents(
                {"history.stage": {"$in": _OLD_VALUES}}
            ),
            "candidate_mappings.history.from_stage": await db.candidate_mappings.count_documents(
                {"history.from_stage": {"$in": _OLD_VALUES}}
            ),
            "candidate_events.from_stage": await db.candidate_events.count_documents(
                {"from_stage": {"$in": _OLD_VALUES}}
            ),
            "candidate_events.to_stage": await db.candidate_events.count_documents(
                {"to_stage": {"$in": _OLD_VALUES}}
            ),
        }
        print("Post-migration verification (should all be 0):")
        for k, v in remaining.items():
            print(f"  {k}: {v}")

    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()
    asyncio.run(_migrate(dry_run=args.dry_run))

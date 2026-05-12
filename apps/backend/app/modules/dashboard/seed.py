"""Seed utility for dashboard collections with realistic demo data."""

from __future__ import annotations

import argparse
import asyncio
import random
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo import AsyncMongoClient

from app.config import settings
from app.modules.dashboard.enums import ActivityType, JobStatus, PipelineStage, TargetEntityType

_EMPLOYEE_NAMES = [
    "Edwin D'Souza",
    "Manokamna Rao",
    "Hardik Patel",
    "Mohit Sharma",
    "Aakash Menon",
    "Sana Khan",
    "Riya Chatterjee",
    "Nikhil Bhat",
    "Tanvi Kulkarni",
    "Arjun Iyer",
    "Priya Nair",
    "Kunal Verma",
]

_CLIENT_NAMES = [
    "ABNAH",
    "August Cafe",
    "Aures Hospitality",
    "Baesic Fit",
    "CocoCart",
    "Dough and Joe",
    "Flavour Pots",
    "Ghost Kitchens",
    "Hunger Inc",
    "Izumi",
    "Kaia",
    "Le 15",
    "Milagro",
    "NOTO",
    "Olive",
    "Pebble Street",
    "Scarlett House",
    "Shalimar Hotel",
    "TAB",
    "TAT",
    "The Ranch",
    "Tropicool",
    "True Palate",
    "Zima",
]

_ROLE_NAMES = [
    "Sous Chef",
    "Restaurant Manager",
    "Commis Chef",
    "Steward",
    "Barista",
    "Captain",
    "Host",
    "Kitchen Assistant",
    "Pastry Chef",
    "Bartender",
]

_SKILLS = [
    "Hospitality",
    "Upselling",
    "Customer Service",
    "POS",
    "Inventory",
    "Kitchen Ops",
    "Food Safety",
    "Communication",
    "Team Leadership",
    "Barista Skills",
    "Mixology",
    "People Management",
]

_COMPANIES = [
    "Hunger Inc",
    "Olive Group",
    "Massive Restaurants",
    "Impresario",
    "Speciality Restaurants",
    "Mainland Group",
    "Independent Outlet",
]

_STAGE_WEIGHTS: list[tuple[PipelineStage, int]] = [
    (PipelineStage.added, 18),
    (PipelineStage.shortlisted, 16),
    (PipelineStage.sent_to_client, 18),
    (PipelineStage.rejected, 9),
    (PipelineStage.hold, 7),
    (PipelineStage.offer_sent, 10),
    (PipelineStage.offer_accepted, 8),
    (PipelineStage.joined, 8),
    (PipelineStage.dropped, 6),
]


def _weighted_stage(rng: random.Random) -> PipelineStage:
    stages = [stage for stage, _ in _STAGE_WEIGHTS]
    weights = [weight for _, weight in _STAGE_WEIGHTS]
    return rng.choices(stages, weights=weights, k=1)[0]


def _rand_time(rng: random.Random, *, min_days: int, max_days: int) -> datetime:
    age_days = rng.randint(min_days, max_days)
    age_hours = rng.randint(0, 23)
    age_minutes = rng.randint(0, 59)
    return datetime.now(UTC) - timedelta(days=age_days, hours=age_hours, minutes=age_minutes)


async def seed_dashboard_data(reset: bool = True, seed: int = 20250119) -> None:
    rng = random.Random(seed)
    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]

    employees_col = db["employees"]
    candidates_col = db["candidates"]
    job_openings_col = db["job_openings"]
    mappings_col = db["candidate_mappings"]
    activities_col = db["activities"]
    documents_col = db["documents"]

    if reset:
        await employees_col.delete_many({})
        await candidates_col.delete_many({})
        await job_openings_col.delete_many({})
        await mappings_col.delete_many({})
        await activities_col.delete_many({})
        await documents_col.delete_many({})

    employee_docs: list[dict[str, Any]] = []
    for name in _EMPLOYEE_NAMES:
        created = _rand_time(rng, min_days=60, max_days=360)
        email_local = name.lower().replace(" ", ".").replace("'", "")
        employee_docs.append(
            {
                "_id": ObjectId(),
                "name": name,
                "email": f"{email_local}@recruitr.demo",
                "mappings": {
                    "offers_received": 0,
                    "joined_candidates": 0,
                    "rejected_candidates": 0,
                },
                "total_mappings": 0,
                "created_at": created,
                "updated_at": created,
                "is_active": True,
            }
        )

    await employees_col.insert_many(employee_docs)

    candidate_docs: list[dict[str, Any]] = []
    for idx in range(120):
        first = [
            "Aarav",
            "Vivaan",
            "Aditya",
            "Ira",
            "Anaya",
            "Diya",
            "Kabir",
            "Reyansh",
            "Nitya",
            "Meera",
        ][idx % 10]
        last = ["Shah", "Verma", "Singh", "Nair", "Pillai", "Rao", "Khan", "Bose", "Iyer", "Gupta"][
            (idx // 3) % 10
        ]
        stage = _weighted_stage(rng)
        created = _rand_time(rng, min_days=15, max_days=220)

        candidate_docs.append(
            {
                "_id": ObjectId(),
                "full_name": f"{first} {last}",
                "email": f"{first.lower()}.{last.lower()}.{idx + 1}@mail.demo",
                "phone": f"+91-98{rng.randint(10000000, 99999999)}",
                "previous_company": rng.choice(_COMPANIES),
                "experience": round(rng.uniform(0.8, 8.5), 1),
                "skills": rng.sample(_SKILLS, k=rng.randint(3, 5)),
                "resume_link": f"https://cdn.demo/resumes/{idx + 1}.pdf",
                "current_stage": stage.value,
                "created_at": created,
                "updated_at": created,
                "is_active": True,
            }
        )

    await candidates_col.insert_many(candidate_docs)

    job_docs: list[dict[str, Any]] = []
    for idx, client_name in enumerate(_CLIENT_NAMES):
        total_seats = rng.randint(2, 12)
        status = rng.choices(
            [JobStatus.open, JobStatus.on_hold, JobStatus.closed],
            weights=[70, 18, 12],
            k=1,
        )[0]
        created = _rand_time(rng, min_days=20, max_days=180)

        job_docs.append(
            {
                "_id": ObjectId(),
                "client_name": client_name,
                "role": rng.choice(_ROLE_NAMES),
                "total_seats": total_seats,
                "filled_seats": 0,
                "remaining_seats": total_seats,
                "status": status.value,
                "created_at": created,
                "updated_at": created,
                "is_active": True,
            }
        )

    await job_openings_col.insert_many(job_docs)

    mapping_docs: list[dict[str, Any]] = []
    pair_guard: set[tuple[ObjectId, ObjectId]] = set()
    stage_per_candidate: dict[ObjectId, tuple[PipelineStage, datetime]] = {}

    for _ in range(260):
        attempts = 0
        candidate = rng.choice(candidate_docs)
        job = rng.choice(job_docs)
        pair = (candidate["_id"], job["_id"])

        while pair in pair_guard and attempts < 12:
            candidate = rng.choice(candidate_docs)
            job = rng.choice(job_docs)
            pair = (candidate["_id"], job["_id"])
            attempts += 1

        if pair in pair_guard:
            continue

        pair_guard.add(pair)
        employee = rng.choice(employee_docs)
        stage = _weighted_stage(rng)
        mapped_at = _rand_time(rng, min_days=0, max_days=90)

        mapping_docs.append(
            {
                "_id": ObjectId(),
                "employee_id": employee["_id"],
                "candidate_id": candidate["_id"],
                "job_opening_id": job["_id"],
                "pipeline_stage": stage.value,
                "mapped_at": mapped_at,
                "updated_at": mapped_at,
            }
        )

        previous = stage_per_candidate.get(candidate["_id"])
        if previous is None or mapped_at > previous[1]:
            stage_per_candidate[candidate["_id"]] = (stage, mapped_at)

    await mappings_col.insert_many(mapping_docs)

    for candidate_id, (stage, updated_at) in stage_per_candidate.items():
        await candidates_col.update_one(
            {"_id": candidate_id},
            {"$set": {"current_stage": stage.value, "updated_at": updated_at}},
        )

    joined_per_job: dict[ObjectId, int] = defaultdict(int)
    for mapping in mapping_docs:
        if mapping["pipeline_stage"] == PipelineStage.joined.value:
            joined_per_job[mapping["job_opening_id"]] += 1

    for job in job_docs:
        joined = min(joined_per_job.get(job["_id"], 0), int(job["total_seats"]))
        remaining = max(int(job["total_seats"]) - joined, 0)
        await job_openings_col.update_one(
            {"_id": job["_id"]},
            {
                "$set": {
                    "filled_seats": joined,
                    "remaining_seats": remaining,
                    "updated_at": datetime.now(UTC),
                }
            },
        )

    offer_sent_per_employee: dict[ObjectId, int] = defaultdict(int)
    joined_per_employee: dict[ObjectId, int] = defaultdict(int)
    rejected_per_employee: dict[ObjectId, int] = defaultdict(int)
    total_per_employee: dict[ObjectId, int] = defaultdict(int)

    for mapping in mapping_docs:
        employee_id: ObjectId = mapping["employee_id"]
        total_per_employee[employee_id] += 1
        if mapping["pipeline_stage"] == PipelineStage.offer_sent.value:
            offer_sent_per_employee[employee_id] += 1
        if mapping["pipeline_stage"] == PipelineStage.joined.value:
            joined_per_employee[employee_id] += 1
        if mapping["pipeline_stage"] == PipelineStage.rejected.value:
            rejected_per_employee[employee_id] += 1

    for employee in employee_docs:
        employee_id = employee["_id"]
        await employees_col.update_one(
            {"_id": employee_id},
            {
                "$set": {
                    "total_mappings": total_per_employee.get(employee_id, 0),
                    "mappings": {
                        "offers_received": offer_sent_per_employee.get(employee_id, 0),
                        "joined_candidates": joined_per_employee.get(employee_id, 0),
                        "rejected_candidates": rejected_per_employee.get(employee_id, 0),
                    },
                    "updated_at": datetime.now(UTC),
                }
            },
        )

    activity_docs: list[dict[str, Any]] = []
    for mapping in sorted(mapping_docs, key=lambda item: item["mapped_at"], reverse=True)[:180]:
        stage = PipelineStage(mapping["pipeline_stage"])
        activity_type = {
            PipelineStage.offer_sent: ActivityType.offer_sent,
            PipelineStage.offer_accepted: ActivityType.offer_accepted,
            PipelineStage.joined: ActivityType.joined,
            PipelineStage.rejected: ActivityType.rejected,
        }.get(stage, ActivityType.mapped)

        job = next((entry for entry in job_docs if entry["_id"] == mapping["job_opening_id"]), None)
        candidate = next((entry for entry in candidate_docs if entry["_id"] == mapping["candidate_id"]), None)
        activity_docs.append(
            {
                "_id": ObjectId(),
                "employee_id": mapping["employee_id"],
                "activity_type": activity_type.value,
                "target_entity_type": TargetEntityType.candidate.value,
                "target_entity_id": str(mapping["candidate_id"]),
                "description": (
                    f"{candidate['full_name']} for {job['client_name']} ({job['role']}) moved to "
                    f"{stage.value.replace('_', ' ')}"
                    if job and candidate
                    else f"Candidate moved to {stage.value.replace('_', ' ')}"
                ),
                "created_at": mapping["mapped_at"],
            }
        )

    await activities_col.insert_many(activity_docs)

    document_docs: list[dict[str, Any]] = []
    for candidate in rng.sample(candidate_docs, k=80):
        uploaded_at = _rand_time(rng, min_days=0, max_days=120)
        document_docs.append(
            {
                "_id": ObjectId(),
                "candidate_id": candidate["_id"],
                "file_name": f"{candidate['full_name'].replace(' ', '_').lower()}_resume.pdf",
                "file_type": "resume",
                "file_url": candidate["resume_link"],
                "uploaded_at": uploaded_at,
            }
        )

    await documents_col.insert_many(document_docs)

    await client.close()
    print("Dashboard seed complete")
    print(f"employees: {len(employee_docs)}")
    print(f"candidates: {len(candidate_docs)}")
    print(f"job_openings: {len(job_docs)}")
    print(f"candidate_mappings: {len(mapping_docs)}")
    print(f"activities: {len(activity_docs)}")
    print(f"documents: {len(document_docs)}")


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Seed dashboard collections")
    parser.add_argument("--no-reset", action="store_true", help="Keep existing data and append")
    parser.add_argument("--seed", type=int, default=20250119, help="Random seed")
    args = parser.parse_args()

    await seed_dashboard_data(reset=not args.no_reset, seed=args.seed)


if __name__ == "__main__":
    asyncio.run(_main())

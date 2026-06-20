"""Demo/development data migration: old dashboard collections → unified recruitment schema.

All migrated entities are assigned to the demo tenant/domain "binge.consulting".
This script is NOT for production use — it requires DEMO_MODE=true to run.
If DEMO_MODE is not "true", the script aborts via sys.exit(1) before touching any data.

Maps data from:
  job_openings  → positions (new fields + requirements backfill)
  candidates    → candidates (rename experience→experience_years, add skills_normalized, brand_id)
  candidate_mappings → candidate_mappings (add brand_id, position_id, client_id; remap stages)
  employees     → employees (add brand_id, user_id=null)
  activities    → activities (add brand_id)
  documents     → documents (add brand_id)

Usage:
    DEMO_MODE=true python -m app.modules.recruitment.migrate
    # Review output, then restart the application.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from pymongo import AsyncMongoClient

from app.config import settings
from app.modules.recruitment.enums import PipelineStage, PositionStatus

# ── Stage remapping (old dashboard PipelineStage → new unified PipelineStage) ──
_STAGE_MAP: dict[str, str] = {
    "added": PipelineStage.sourced.value,
    "shortlisted": PipelineStage.sourced.value,
    "sent_to_client": PipelineStage.sent_to_client.value,
    "rejected": PipelineStage.rejected.value,
    "dropped": PipelineStage.rejected.value,
    "hold": PipelineStage.on_hold.value,
    "offer_sent": PipelineStage.offer.value,
    "offer_accepted": PipelineStage.offer_accepted.value,
    "joined": PipelineStage.position_close.value,
}

_STATUS_MAP: dict[str, str] = {
    "open": PositionStatus.open.value,
    "closed": PositionStatus.closed.value,
    "on_hold": PositionStatus.on_hold.value,
}

# Role → requirements (same as seed defaults)
_ROLE_REQUIREMENTS: dict[str, list[str]] = {
    "steward": ["service", "table", "guest", "pos", "billing"],
    "captain": ["service", "table", "guest", "pos", "billing", "team leadership"],
    "bartender": ["mixology", "cocktail", "pouring", "bar", "speed pouring"],
    "barista": ["barista skills", "espresso", "customer service", "coffee"],
    "commis chef": ["chef", "food safety", "cooking", "prep work"],
    "sous chef": ["chef", "oven", "cuisine", "food safety", "cooking", "kitchen management"],
    "pastry chef": ["pastry", "baking", "food safety", "cuisine"],
    "restaurant manager": ["operations", "management", "scheduling", "p&l", "staff"],
    "kitchen assistant": ["kitchen ops", "food safety", "prep work", "cooking"],
    "host": ["guest relations", "customer service", "communication"],
}


def _backfill_requirements(role: str) -> list[str]:
    return _ROLE_REQUIREMENTS.get(role.lower().strip(), ["hospitality", "communication"])


async def migrate() -> None:
    if os.getenv("DEMO_MODE", "false").lower() != "true":
        print("Migration aborted: DEMO_MODE flag is not 'true'.")
        print("Production data must not be mass-updated to the demo tenant.")
        sys.exit(1)

    client = AsyncMongoClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    now = datetime.now(UTC)

    # ── 1. Create (or find) demo brand ────────────────────────────────────────
    existing_brand = await db["brands"].find_one({"domain": "binge.consulting"})
    if existing_brand:
        brand_id: ObjectId = existing_brand["_id"]
        print(f"Using existing brand: {existing_brand['name']} ({brand_id})")
    else:
        brand_id = ObjectId()
        await db["brands"].insert_one(
            {
                "_id": brand_id,
                "owner_id": "migrate",
                "name": "Binge Consulting",
                "domain": "binge.consulting",
                "branding": {"logo_public_id": None, "logo_url": None},
                "created_at": now,
            }
        )
        print(f"Created brand: Binge Consulting ({brand_id})")

    # ── 2. Backfill employees with brand_id ───────────────────────────────────
    emp_result = await db["employees"].update_many(
        {"brand_id": {"$exists": False}},
        {"$set": {"brand_id": brand_id, "user_id": None, "updated_at": now}},
    )
    print(f"Employees backfilled: {emp_result.modified_count}")

    # ── 3. Create clients from distinct job_openings.client_name ──────────────
    job_openings = await db["job_openings"].find({}).to_list(length=None)
    existing_clients = {
        c["name"]: c for c in await db["clients"].find({"brand_id": brand_id}).to_list(length=None)
    }

    client_name_to_id: dict[str, ObjectId] = {
        name: doc["_id"] for name, doc in existing_clients.items()
    }
    client_seq = max(
        (
            int(c["code"].split("-")[1])
            for c in existing_clients.values()
            if "-" in c.get("code", "")
        ),
        default=0,
    )

    new_clients: list[dict[str, Any]] = []
    for job in job_openings:
        name = job.get("client_name", "Unknown")
        if name not in client_name_to_id:
            client_seq += 1
            code = f"CLI-{client_seq:03d}"
            cid = ObjectId()
            new_clients.append(
                {
                    "_id": cid,
                    "brand_id": brand_id,
                    "code": code,
                    "name": name,
                    "city": None,
                    "logo_url": None,
                    "is_active": True,
                    "created_at": job.get("created_at", now),
                    "updated_at": now,
                }
            )
            client_name_to_id[name] = cid

    if new_clients:
        await db["clients"].insert_many(new_clients)
    print(f"Clients created: {len(new_clients)}")

    # ── 4. Create positions from job_openings ─────────────────────────────────
    # Build client_id → pos sequence counter
    pos_seq_by_client: dict[ObjectId, int] = {}
    job_opening_to_position: dict[ObjectId, ObjectId] = {}

    position_docs: list[dict[str, Any]] = []
    for job in job_openings:
        client_id = client_name_to_id.get(job.get("client_name", ""), ObjectId())
        pos_seq_by_client[client_id] = pos_seq_by_client.get(client_id, 0) + 1
        seq = pos_seq_by_client[client_id]

        # Derive client code
        client_doc = next(
            (c for c in (new_clients + list(existing_clients.values())) if c["_id"] == client_id),
            None,
        )
        client_code = client_doc["code"] if client_doc else "CLI-000"
        pos_code = f"{client_code}-POS-{seq:03d}"
        pos_id = ObjectId()
        job_opening_to_position[job["_id"]] = pos_id

        old_status = job.get("status", "open")
        new_status = _STATUS_MAP.get(old_status, PositionStatus.open.value)
        role = job.get("role", "")
        total = int(job.get("total_seats", 0))
        filled = int(job.get("filled_seats", 0))

        position_docs.append(
            {
                "_id": pos_id,
                "brand_id": brand_id,
                "code": pos_code,
                "client_id": client_id,
                "client_name": job.get("client_name", ""),
                "role": role,
                "department": None,
                "city": None,
                "seniority": "Mid",
                "requirements": _backfill_requirements(role),
                "total_seats": total,
                "filled_seats": filled,
                "remaining_seats": max(total - filled, 0),
                "status": new_status,
                "assigned_employee_id": None,
                "date_opened": job.get("created_at", now),
                "target_close": None,
                "notes": None,
                "is_active": True,
                "created_at": job.get("created_at", now),
                "updated_at": now,
            }
        )

    if position_docs:
        await db["positions"].insert_many(position_docs)
    print(f"Positions created: {len(position_docs)}")

    # ── 5. Backfill candidates ────────────────────────────────────────────────
    cand_result = await db["candidates"].update_many(
        {"brand_id": {"$exists": False}},
        [
            {
                "$set": {
                    "brand_id": brand_id,
                    "experience_years": {"$ifNull": ["$experience", 0]},
                    "skills_normalized": {
                        "$map": {
                            "input": {"$ifNull": ["$skills", []]},
                            "as": "s",
                            "in": {"$toLower": "$$s"},
                        }
                    },
                    "current_stage": {
                        "$switch": {
                            "branches": [
                                {
                                    "case": {"$eq": ["$current_stage", "added"]},
                                    "then": PipelineStage.sourced.value,
                                },
                                {
                                    "case": {"$eq": ["$current_stage", "shortlisted"]},
                                    "then": PipelineStage.sourced.value,
                                },
                                {
                                    "case": {"$eq": ["$current_stage", "offer_sent"]},
                                    "then": PipelineStage.offer.value,
                                },
                                {
                                    "case": {"$eq": ["$current_stage", "joined"]},
                                    "then": PipelineStage.position_close.value,
                                },
                                {
                                    "case": {"$eq": ["$current_stage", "dropped"]},
                                    "then": PipelineStage.rejected.value,
                                },
                                {
                                    "case": {"$eq": ["$current_stage", "hold"]},
                                    "then": PipelineStage.on_hold.value,
                                },
                            ],
                            "default": "$current_stage",
                        }
                    },
                    "updated_at": now,
                }
            }
        ],
    )
    print(f"Candidates backfilled: {cand_result.modified_count}")

    # ── 6. Backfill candidate_mappings ────────────────────────────────────────
    mappings = await db["candidate_mappings"].find({}).to_list(length=None)
    for m in mappings:
        old_stage = m.get("pipeline_stage", "added")
        new_stage = _STAGE_MAP.get(old_stage, PipelineStage.sourced.value)
        old_job_id: ObjectId = m.get("job_opening_id")
        new_pos_id = job_opening_to_position.get(old_job_id)

        update: dict[str, Any] = {
            "brand_id": brand_id,
            "stage": new_stage,
            "decision": "pending",
            "history": [
                {
                    "stage": new_stage,
                    "decision": "pending",
                    "by_employee_id": m.get("employee_id"),
                    "at": m.get("mapped_at", now),
                }
            ],
            "updated_at": now,
        }
        if new_pos_id:
            update["position_id"] = new_pos_id
            # Find client_id from position
            pos = next((p for p in position_docs if p["_id"] == new_pos_id), None)
            if pos:
                update["client_id"] = pos["client_id"]

        await db["candidate_mappings"].update_one({"_id": m["_id"]}, {"$set": update})

    print(f"Mappings backfilled: {len(mappings)}")

    # ── 7. Backfill activities and documents ──────────────────────────────────
    act_result = await db["activities"].update_many(
        {"brand_id": {"$exists": False}},
        {"$set": {"brand_id": brand_id, "activity_type": "mapped"}},
    )
    doc_result = await db["documents"].update_many(
        {"brand_id": {"$exists": False}},
        {"$set": {"brand_id": brand_id}},
    )
    print(f"Activities backfilled: {act_result.modified_count}")
    print(f"Documents backfilled: {doc_result.modified_count}")

    # ── 8. Seed counters ──────────────────────────────────────────────────────
    await db["counters"].update_one(
        {"brand_id": brand_id, "key": "client"},
        {"$set": {"seq": client_seq}},
        upsert=True,
    )
    print("Counters seeded.")

    await client.close()
    print("\n✓ Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())

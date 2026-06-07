"""Fresh seed for the unified recruitment collections.

Populates a single demo brand "Binge Consulting" with clients, positions,
candidates, and mappings that mirror the frontend mock data exactly, so the
"AI Ranked" match panel and Kanban pipeline are immediately functional.

Usage:
    cd apps/backend
    python -m app.modules.recruitment.seed            # reset + reseed
    python -m app.modules.recruitment.seed --no-reset # append only
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.config import settings
from app.modules.recruitment.enums import (
    ActivityType,
    Decision,
    EducationLevel,
    PipelineStage,
    PositionStatus,
    Seniority,
)

# ── Repeated string constants ──────────────────────────────────────────────────

_DEPT_FNB_SERVICE = "F&B - Service"
_EMAIL_PRIYA = "priya.nair@example.com"
_EMAIL_KARAN = "karan.m@example.com"
_EMAIL_SNEHA = "sneha.g@example.com"

# ── Demo data ──────────────────────────────────────────────────────────────────

_BRAND = {"name": "Binge Consulting", "domain": "binge.consulting"}

_EMPLOYEES = [
    {
        "name": "Edwin D'Souza",
        "email": "edwin.dsouza@binge.consulting",
        "team": "Kitchen & Operations",
    },
    {"name": "Mohit Sharma", "email": "mohit.sharma@binge.consulting", "team": "F&B Service"},
    {"name": "Aakash Menon", "email": "aakash.menon@binge.consulting", "team": "F&B Service"},
    {
        "name": "Manokamna Rao",
        "email": "manokamna.rao@binge.consulting",
        "team": "Kitchen & Operations",
    },
    {"name": "Hardik Patel", "email": "hardik.patel@binge.consulting", "team": "Marketing"},
    {"name": "Sana Khan", "email": "sana.khan@binge.consulting", "team": "Management"},
]

_TEAMS = ["Kitchen & Operations", "F&B Service", "Marketing", "Management"]
_TAGS = [
    "Immediate Joiner",
    "Good Communicator",
    "High Potential",
    "Relocation Willing",
    "Premium Background",
]

# (client_seq, client_name, city)
_CLIENTS = [
    (1, "ABNAH", "Mumbai"),
    (14, "Blondie", "Mumbai"),
    (16, "CocoCart", "Mumbai"),
    (26, "Foodmatters", "Mumbai"),
    (31, "Hunger Inc", "Mumbai"),
    (71, "UGIPL", "Mumbai"),
]

_ROLE_REQUIREMENTS: dict[str, list[str]] = {
    "steward": ["service", "table", "guest", "pos", "billing", "hospitality"],
    "captain": ["service", "table", "guest", "pos", "billing", "team leadership"],
    "cafe steward": ["service", "table", "guest", "pos", "billing", "hospitality"],
    "bartender": [
        "mixology",
        "cocktail",
        "pouring",
        "bar",
        "speed pouring",
        "inventory management",
    ],
    "gre": ["guest relations", "customer service", "communication", "hospitality"],
    "arm": ["operations", "management", "scheduling", "staff", "customer satisfaction"],
    "rm": ["operations", "management", "scheduling", "p&l", "staff"],
    "operations head": ["operations", "management", "p&l", "staff scheduling", "admin"],
    "social media manager": [
        "instagram marketing",
        "content creation",
        "canva",
        "brand strategy",
        "digital ads",
    ],
    "f&b associate": ["f&b service", "hospitality", "customer service", "service", "pos"],
    "sous chef": ["chef", "oven", "cuisine", "food safety", "cooking", "kitchen management"],
    "outlet supervisor": ["supervision", "operations", "management", "scheduling", "staff"],
}


def _reqs(role: str) -> list[str]:
    return _ROLE_REQUIREMENTS.get(role.lower(), ["hospitality", "communication"])


# (client_code, role, dept, seniority, seats, status, emp_idx, notes, pos_seq)
_POSITIONS = [
    (
        "CLI-031",
        "Cafe Steward",
        _DEPT_FNB_SERVICE,
        Seniority.junior,
        7,
        PositionStatus.open,
        0,
        None,
        1,
    ),
    ("CLI-031", "Captain", _DEPT_FNB_SERVICE, Seniority.junior, 7, PositionStatus.open, 0, None, 2),
    (
        "CLI-026",
        "Captain",
        _DEPT_FNB_SERVICE,
        Seniority.junior,
        0,
        PositionStatus.closed,
        0,
        None,
        1,
    ),
    ("CLI-026", "Steward", _DEPT_FNB_SERVICE, Seniority.junior, 8, PositionStatus.open, 0, None, 2),
    (
        "CLI-026",
        "Bartender",
        _DEPT_FNB_SERVICE,
        Seniority.junior,
        0,
        PositionStatus.closed,
        0,
        None,
        3,
    ),
    ("CLI-001", "Steward", _DEPT_FNB_SERVICE, Seniority.junior, 5, PositionStatus.open, 1, None, 1),
    ("CLI-001", "GRE", _DEPT_FNB_SERVICE, Seniority.junior, 3, PositionStatus.open, 1, None, 2),
    (
        "CLI-001",
        "Bartender",
        _DEPT_FNB_SERVICE,
        Seniority.junior,
        3,
        PositionStatus.open,
        1,
        None,
        3,
    ),
    ("CLI-014", "ARM", _DEPT_FNB_SERVICE, Seniority.mid, 3, PositionStatus.open, 2, None, 1),
    ("CLI-014", "RM", _DEPT_FNB_SERVICE, Seniority.mid, 3, PositionStatus.open, 2, None, 2),
    (
        "CLI-014",
        "Operations Head",
        "Operations",
        Seniority.senior,
        1,
        PositionStatus.closed,
        2,
        None,
        3,
    ),
    (
        "CLI-014",
        "Social Media Manager",
        "Marketing & PR",
        Seniority.junior,
        2,
        PositionStatus.open,
        2,
        None,
        4,
    ),
    (
        "CLI-016",
        "F&B Associate",
        _DEPT_FNB_SERVICE,
        Seniority.junior,
        35,
        PositionStatus.open,
        1,
        None,
        1,
    ),
    (
        "CLI-071",
        "Sous Chef",
        "F&B - Kitchen",
        Seniority.senior,
        1,
        PositionStatus.open,
        1,
        "Pizza Chef",
        1,
    ),
    (
        "CLI-071",
        "Outlet Supervisor",
        _DEPT_FNB_SERVICE,
        Seniority.mid,
        3,
        PositionStatus.open,
        3,
        None,
        2,
    ),
    ("CLI-071", "Steward", _DEPT_FNB_SERVICE, Seniority.junior, 8, PositionStatus.open, 3, None, 3),
]

# (name, email, phone, company, exp_years, skills[])
_CANDIDATES = [
    (
        "Priya Nair",
        _EMAIL_PRIYA,
        "+91 98765 43210",
        "The Taj Mahal Palace",
        2.0,
        ["Guest Relations", "Table Service", "POS Systems", "Order Taking", "Billing"],
    ),
    (
        "Karan Malhotra",
        _EMAIL_KARAN,
        "+91 98123 45678",
        "JW Marriott Mumbai",
        3.0,
        ["F&B Service", "Fine Dining", "Banquets", "Team Leadership", "Service"],
    ),
    (
        "Sneha Gupta",
        _EMAIL_SNEHA,
        "+91 97654 32109",
        "Leela Palace",
        1.5,
        ["Hostess", "Table Reservation", "Billing", "Guest Relations", "POS"],
    ),
    (
        "Sunil Mehta",
        "sunil.bartender@example.com",
        "+91 99887 76655",
        "Trident Nariman Point",
        4.0,
        ["Mixology", "Classic Cocktails", "Inventory Management", "Speed Pouring", "Bar"],
    ),
    (
        "Rajesh Kumar",
        "chef.rajesh@example.com",
        "+91 95555 44444",
        "Pizza Express Mumbai",
        6.0,
        ["Pizza Dough Crafting", "Wood-fired Oven", "Italian Cuisine", "Food Safety", "Cooking"],
    ),
    (
        "Amit Sharma",
        "amit.souschef@example.com",
        "+91 94444 33333",
        "Oberoi Hotels",
        5.0,
        ["Sous Chef", "Kitchen Management", "Continental Cuisine", "Plating", "Food Safety"],
    ),
    (
        "Vikram Singh",
        "vikram.cook@example.com",
        "+91 93333 22222",
        "Local Dhaba Elite",
        3.0,
        ["Tandoor Cook", "Indian Curry", "Bulk Cooking", "Prep Work", "Cooking"],
    ),
    (
        "Rohan Joshi",
        "rohan.joshi@example.com",
        "+91 92222 11111",
        "Olive Bar & Kitchen",
        8.0,
        [
            "Restaurant Operations",
            "P&L Management",
            "Staff Scheduling",
            "Customer Satisfaction",
            "Management",
        ],
    ),
    (
        "Nisha Rao",
        "nisha.ops@example.com",
        "+91 91111 00000",
        "Social Offline",
        4.5,
        [
            "Assistant Manager",
            "Inventory Audits",
            "Staff Training",
            "Escalation Handling",
            "Operations",
        ],
    ),
    (
        "Ananya Sen",
        "ananya.marketing@example.com",
        "+91 90000 99999",
        "F&B Marketing Agency",
        3.0,
        ["Instagram Marketing", "Content Creation", "Canva", "Brand Strategy", "Digital Ads"],
    ),
    (
        "Rahul Verma",
        "rahul.ads@example.com",
        "+91 89999 88888",
        "Freelance Brand Specialist",
        2.0,
        ["Digital Ads (Meta/Google)", "Graphic Design", "Video Reels Editing", "Analytics"],
    ),
]

# (position_code, candidate_email, stage)
_MAPPINGS = [
    ("CLI-031-POS-001", _EMAIL_PRIYA, PipelineStage.sent_to_client),
    ("CLI-031-POS-001", _EMAIL_SNEHA, PipelineStage.sourced),
    ("CLI-031-POS-002", _EMAIL_KARAN, PipelineStage.interview),
    ("CLI-026-POS-002", _EMAIL_PRIYA, PipelineStage.sourced),
    ("CLI-001-POS-001", _EMAIL_KARAN, PipelineStage.sent_to_client),
    ("CLI-001-POS-001", _EMAIL_SNEHA, PipelineStage.decision_pending),
    ("CLI-014-POS-004", "ananya.marketing@example.com", PipelineStage.offer),
    ("CLI-071-POS-001", "chef.rajesh@example.com", PipelineStage.offer_accepted),
    ("CLI-071-POS-001", "amit.souschef@example.com", PipelineStage.sourced),
    ("CLI-001-POS-003", "sunil.bartender@example.com", PipelineStage.sent_to_client),
    ("CLI-016-POS-001", _EMAIL_PRIYA, PipelineStage.sourced),
]


# ── Seed helpers (each inserts one logical group) ─────────────────────────────


async def _seed_brand(db: AsyncDatabase, now: datetime) -> ObjectId:
    brand_id = ObjectId()
    await db["brands"].insert_one(
        {
            "_id": brand_id,
            "owner_id": "seed",
            "name": _BRAND["name"],
            "domain": _BRAND["domain"],
            "branding": {"logo_public_id": None, "logo_url": None},
            "created_at": now,
        }
    )
    print(f"Brand: {_BRAND['name']} ({brand_id})")
    return brand_id


async def _seed_teams(db: AsyncDatabase, brand_id: ObjectId, now: datetime) -> dict[str, ObjectId]:
    team_docs = []
    team_map = {}
    for name in _TEAMS:
        tid = ObjectId()
        team_docs.append(
            {
                "_id": tid,
                "brand_id": brand_id,
                "name": name,
                "is_active": True,
                "created_at": now - timedelta(days=60),
                "updated_at": now - timedelta(days=60),
            }
        )
        team_map[name] = tid
    await db["teams"].insert_many(team_docs)
    print(f"Teams: {len(team_docs)}")
    return team_map


async def _seed_tags(db: AsyncDatabase, brand_id: ObjectId, now: datetime) -> None:
    tag_docs = [
        {
            "_id": ObjectId(),
            "brand_id": brand_id,
            "name": name,
            "is_active": True,
            "created_at": now - timedelta(days=60),
            "updated_at": now - timedelta(days=60),
        }
        for name in _TAGS
    ]
    await db["recruiter_tags"].insert_many(tag_docs)
    print(f"Recruiter Tags: {len(tag_docs)}")


async def _seed_employees(
    db: AsyncDatabase, brand_id: ObjectId, team_map: dict[str, ObjectId], now: datetime
) -> list[dict[str, Any]]:
    emp_docs = [
        {
            "_id": ObjectId(),
            "brand_id": brand_id,
            "user_id": None,
            "team_id": team_map.get(emp.get("team", "")),
            "name": emp["name"],
            "email": emp["email"],
            "avatar_url": None,
            "is_active": True,
            "created_at": now - timedelta(days=60),
            "updated_at": now - timedelta(days=60),
        }
        for emp in _EMPLOYEES
    ]
    await db["employees"].insert_many(emp_docs)
    print(f"Employees: {len(emp_docs)}")
    return emp_docs


async def _seed_clients(
    db: AsyncDatabase, brand_id: ObjectId, now: datetime
) -> tuple[list[dict[str, Any]], dict[str, ObjectId], int, dict[str, str]]:
    client_docs: list[dict[str, Any]] = []
    client_map: dict[str, ObjectId] = {}
    max_seq = 0
    for seq, name, city in _CLIENTS:
        code = f"CLI-{seq:03d}"
        cid = ObjectId()
        client_docs.append(
            {
                "_id": cid,
                "brand_id": brand_id,
                "code": code,
                "name": name,
                "city": city,
                "logo_url": None,
                "is_active": True,
                "created_at": now - timedelta(days=45),
                "updated_at": now - timedelta(days=45),
            }
        )
        client_map[code] = cid
        max_seq = max(max_seq, seq)
    await db["clients"].insert_many(client_docs)
    print(f"Clients: {len(client_docs)}")
    client_name_map = {f"CLI-{seq:03d}": name for seq, name, _ in _CLIENTS}
    return client_docs, client_map, max_seq, client_name_map


async def _seed_positions(
    db: AsyncDatabase,
    brand_id: ObjectId,
    emp_docs: list[dict[str, Any]],
    client_map: dict[str, ObjectId],
    client_name_map: dict[str, str],
    now: datetime,
) -> tuple[list[dict[str, Any]], dict[str, ObjectId], dict[str, int]]:
    position_docs: list[dict[str, Any]] = []
    position_code_to_id: dict[str, ObjectId] = {}
    max_pos_seq: dict[str, int] = {}
    for idx, (
        c_code,
        role,
        dept,
        seniority,
        seats,
        pos_status,
        emp_idx,
        notes,
        pos_seq,
    ) in enumerate(_POSITIONS):
        code = f"{c_code}-POS-{pos_seq:03d}"
        train_line = ["Western", "Central", "Harbor"][idx % 3]
        pid = ObjectId()
        position_docs.append(
            {
                "_id": pid,
                "brand_id": brand_id,
                "code": code,
                "client_id": client_map[c_code],
                "client_name": client_name_map[c_code],
                "role": role,
                "department": dept,
                "city": "Mumbai",
                "train_line": train_line,
                "seniority": seniority.value,
                "requirements": _reqs(role),
                "total_seats": seats,
                "filled_seats": 0,
                "remaining_seats": seats,
                "status": pos_status.value,
                "assigned_employee_id": emp_docs[emp_idx]["_id"],
                "date_opened": now - timedelta(days=30),
                "target_close": now + timedelta(days=30),
                "notes": notes,
                "is_active": True,
                "created_at": now - timedelta(days=30),
                "updated_at": now - timedelta(days=30),
            }
        )
        position_code_to_id[code] = pid
        max_pos_seq[c_code] = max(max_pos_seq.get(c_code, 0), pos_seq)
    await db["positions"].insert_many(position_docs)
    print(f"Positions: {len(position_docs)}")
    return position_docs, position_code_to_id, max_pos_seq


async def _seed_candidates(
    db: AsyncDatabase, brand_id: ObjectId, now: datetime
) -> tuple[list[dict[str, Any]], dict[str, ObjectId]]:
    candidate_docs: list[dict[str, Any]] = []
    cand_email_to_id: dict[str, ObjectId] = {}
    for idx, (full_name, email, phone, company, exp_years, skills) in enumerate(_CANDIDATES):
        cid = ObjectId()
        ed_level = [
            EducationLevel.bachelors.value,
            EducationLevel.high_school.value,
            EducationLevel.masters.value,
        ][idx % 3]
        train_line = ["Western", "Central", "Harbor"][(idx + 1) % 3]
        tags = ["Immediate Joiner"] if idx % 2 == 0 else ["Good Communicator"]
        candidate_docs.append(
            {
                "_id": cid,
                "brand_id": brand_id,
                "full_name": full_name,
                "email": email,
                "phone": phone,
                "previous_company": company,
                "experience_years": exp_years,
                "education_level": ed_level,
                "skills": skills,
                "skills_normalized": [s.lower() for s in skills],
                "ai_tags": [],
                "recruiter_tags": tags,
                "preferred_train_line": train_line,
                "resume_url": None,
                "resume_public_id": None,
                "resume_raw_text": None,
                "current_stage": PipelineStage.sourced.value,
                "is_active": True,
                "created_at": now - timedelta(days=20),
                "updated_at": now - timedelta(days=20),
            }
        )
        cand_email_to_id[email] = cid
    await db["candidates"].insert_many(candidate_docs)
    print(f"Candidates: {len(candidate_docs)}")
    return candidate_docs, cand_email_to_id


async def _seed_mappings(
    db: AsyncDatabase,
    brand_id: ObjectId,
    emp_docs: list[dict[str, Any]],
    position_docs: list[dict[str, Any]],
    position_code_to_id: dict[str, ObjectId],
    cand_email_to_id: dict[str, ObjectId],
    now: datetime,
) -> list[dict[str, Any]]:
    pos_by_id = {p["_id"]: p for p in position_docs}
    mapping_docs: list[dict[str, Any]] = []
    seen: set[tuple[ObjectId, ObjectId]] = set()
    for pos_code, cand_email, stage in _MAPPINGS:
        pos_id = position_code_to_id.get(pos_code)
        cand_id = cand_email_to_id.get(cand_email)
        if not pos_id or not cand_id or (cand_id, pos_id) in seen:
            continue
        seen.add((cand_id, pos_id))
        pos_doc = pos_by_id.get(pos_id, {})
        emp_id = pos_doc.get("assigned_employee_id", emp_docs[0]["_id"])
        mapping_docs.append(
            {
                "_id": ObjectId(),
                "brand_id": brand_id,
                "candidate_id": cand_id,
                "position_id": pos_id,
                "client_id": pos_doc.get("client_id"),
                "employee_id": emp_id,
                "stage": stage.value,
                "decision": Decision.pending.value,
                "match_score": None,
                "feedback": None,
                "history": [
                    {
                        "stage": PipelineStage.sourced.value,
                        "decision": Decision.pending.value,
                        "by_employee_id": emp_id,
                        "at": now - timedelta(days=15),
                    }
                ],
                "mapped_at": now - timedelta(days=15),
                "updated_at": now - timedelta(days=5),
            }
        )
    await db["candidate_mappings"].insert_many(mapping_docs)
    print(f"Mappings: {len(mapping_docs)}")
    return mapping_docs


async def _seed_activities(
    db: AsyncDatabase,
    brand_id: ObjectId,
    mapping_docs: list[dict[str, Any]],
    position_docs: list[dict[str, Any]],
    candidate_docs: list[dict[str, Any]],
) -> None:
    pos_by_id = {p["_id"]: p for p in position_docs}
    cand_by_id = {c["_id"]: c for c in candidate_docs}
    activity_docs = []
    for m in mapping_docs:
        pos_doc = pos_by_id.get(m["position_id"])
        cand_doc = cand_by_id.get(m["candidate_id"])
        if not pos_doc or not cand_doc:
            continue
        activity_docs.append(
            {
                "_id": ObjectId(),
                "brand_id": brand_id,
                "employee_id": m["employee_id"],
                "activity_type": ActivityType.mapped.value,
                "target_entity_type": "candidate",
                "target_entity_id": str(m["candidate_id"]),
                "description": (
                    f"{cand_doc['full_name']} mapped to {pos_doc['role']} "
                    f"@ {pos_doc['client_name']} ({m['stage'].replace('_', ' ')})"
                ),
                "created_at": m["mapped_at"],
            }
        )
    await db["activities"].insert_many(activity_docs)
    print(f"Activities: {len(activity_docs)}")


async def _seed_counters(
    db: AsyncDatabase,
    brand_id: ObjectId,
    max_client_seq: int,
    max_pos_seq: dict[str, int],
) -> None:
    counter_docs: list[dict[str, Any]] = [
        {"_id": ObjectId(), "brand_id": brand_id, "key": "client", "seq": max_client_seq}
    ]
    for c_code, max_seq in max_pos_seq.items():
        counter_docs.append(
            {
                "_id": ObjectId(),
                "brand_id": brand_id,
                "key": f"position:{c_code}",
                "seq": max_seq,
            }
        )
    await db["counters"].insert_many(counter_docs)
    print(f"Counters: {len(counter_docs)}")


# ── Main seed entry point ──────────────────────────────────────────────────────


async def seed(*, reset: bool = True) -> None:
    mongo = AsyncMongoClient(settings.MONGODB_URI)
    db = mongo[settings.MONGODB_DB_NAME]

    if reset:
        for col in [
            "candidates",
            "candidate_mappings",
            "positions",
            "clients",
            "employees",
            "teams",
            "recruiter_tags",
            "activities",
            "documents",
            "counters",
        ]:
            await db[col].drop()
        for col in ["brands", "employee_stats", "recruiter_activity"]:
            await db[col].delete_many({})
        print("Cleared existing collections.")

    now = datetime.now(UTC)
    brand_id = await _seed_brand(db, now)
    team_map = await _seed_teams(db, brand_id, now)
    await _seed_tags(db, brand_id, now)
    emp_docs = await _seed_employees(db, brand_id, team_map, now)
    _, client_map, max_client_seq, client_name_map = await _seed_clients(db, brand_id, now)
    position_docs, pos_code_to_id, max_pos_seq = await _seed_positions(
        db, brand_id, emp_docs, client_map, client_name_map, now
    )
    candidate_docs, cand_email_to_id = await _seed_candidates(db, brand_id, now)
    mapping_docs = await _seed_mappings(
        db, brand_id, emp_docs, position_docs, pos_code_to_id, cand_email_to_id, now
    )
    await _seed_activities(db, brand_id, mapping_docs, position_docs, candidate_docs)
    await _seed_counters(db, brand_id, max_client_seq, max_pos_seq)

    await mongo.close()
    print("\n✓ Seed complete — run the app and log in with a seeded employee email to start.")


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Seed the unified recruitment collections.")
    parser.add_argument("--no-reset", action="store_true", help="Append without clearing first")
    args = parser.parse_args()
    await seed(reset=not args.no_reset)


if __name__ == "__main__":
    asyncio.run(_main())

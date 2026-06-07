"""Seed script — loads Excel data into the local MongoDB for dev/testing.

Usage (from monorepo root):
    python specs/data/seed.py

Requires: motor, beanie, pandas, openpyxl
Install:  pip install motor beanie pandas openpyxl

The script is idempotent: re-running clears and re-inserts all seeded data.
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from beanie import init_beanie
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

# ── Paths ───────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

DATA_DIR = Path(__file__).parent
RECRUITMENT_FILE = DATA_DIR / "Binge - Recruitment Dashboard (1).xlsx"
MANPOWER_FILE = DATA_DIR / "Binge - Manpower Database - Combined.xlsx"

# ── Config ──────────────────────────────────────────────────────────────────────

from app.config import settings

BRAND_NAME = "Binge Consulting"


# ── Stage / Status / Seniority maps ─────────────────────────────────────────────

STAGE_MAP: dict[str, str] = {
    "sourced": "sourced",
    "sent to client": "sent_to_client",
    "interview scheduled": "interview",
    "result awaited": "decision_pending",
    "selected": "decision_pending",
    "offer sent": "offer",
    "offer accepted": "offer_accepted",
    "joined": "position_close",
    "rejected": "rejected",
    "candidate dropped": "rejected",
    "hold": "on_hold",
    "on hold": "on_hold",
}

DECISION_MAP: dict[str, str] = {
    "selected": "selected",
    "rejected": "rejected",
    "candidate dropped": "rejected",
    "joined": "selected",
    "offer accepted": "selected",
}

STATUS_MAP: dict[str, str] = {
    "open": "open",
    "on hold": "on_hold",
    "closed": "closed",
    "closed - filled": "closed",
    "closed - cancelled": "closed",
}

SENIORITY_MAP: dict[str, str] = {
    "junior": "Junior",
    "mid": "Mid",
    "senior": "Senior",
    "leadership": "Senior",  # no Leadership tier in enum — nearest match
    "trainee": "Junior",
}

# ── Helpers ──────────────────────────────────────────────────────────────────────


def _clean(val: object) -> str | None:
    if pd.isna(val) or str(val).strip() == "":
        return None
    return str(val).strip()


def _slug(name: str) -> str:
    """'Lakshita Shaw' → 'lakshita.shaw'"""
    parts = re.sub(r"[^a-z0-9 ]", "", name.lower()).split()
    return ".".join(parts) if parts else name.lower()


def _fake_email(name: str, suffix: str = "binge.internal") -> str:
    return f"{_slug(name)}@{suffix}"


def _parse_date(val: object) -> datetime | None:
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=UTC)
    try:
        return pd.to_datetime(val).to_pydatetime().replace(tzinfo=UTC)
    except Exception:
        return None


def _map_stage(raw: str | None) -> str:
    if not raw:
        return "sourced"
    return STAGE_MAP.get(raw.strip().lower(), "sourced")


def _map_decision(raw: str | None) -> str:
    if not raw:
        return "pending"
    return DECISION_MAP.get(raw.strip().lower(), "pending")


def _map_status(raw: str | None) -> str:
    if not raw:
        return "open"
    return STATUS_MAP.get(raw.strip().lower(), "open")


def _map_seniority(raw: str | None) -> str:
    if not raw:
        return "Mid"
    return SENIORITY_MAP.get(raw.strip().lower(), "Mid")


def _exp_years(val: object) -> float:
    s = str(val).lower() if not pd.isna(val) else ""
    if "fresh" in s or s == "0":
        return 0.0
    if "0-6" in s:
        return 0.25
    if "6 month" in s:
        return 0.75
    if "1-2" in s:
        return 1.5
    if "more than 2" in s or "2+" in s:
        return 3.0
    return 0.0


# ── Excel loaders ────────────────────────────────────────────────────────────────


def load_positions() -> pd.DataFrame:
    df = pd.read_excel(RECRUITMENT_FILE, sheet_name="Open Positions", header=1)
    df.columns = df.iloc[0].tolist()
    df = df.iloc[1:].reset_index(drop=True)
    cols = [
        "Position ID", "Client Name", "Role", "Department", "City",
        "Seniority", "Date Opened", "Target Close", "Assigned To",
        "No. of Openings", "Status", "Remarks", "Client ID", "Filled", "Remaining",
    ]
    df = df[cols].dropna(subset=["Position ID"])
    df = df[df["Position ID"].str.startswith("CLI-", na=False)]
    return df.reset_index(drop=True)


def load_pipeline() -> pd.DataFrame:
    df = pd.read_excel(RECRUITMENT_FILE, sheet_name="Candidate Pipeline", header=1)
    df.columns = df.iloc[0].tolist()
    df = df.iloc[1:].reset_index(drop=True)
    cols = [
        "Pipeline ID", "DB Cand ID", "Candidate Name", "Client Name", "Client ID",
        "Role Applied For", "Current Company", "City", "Stage",
        "Sourced By", "Date Added", "Last Updated", "Next Follow-up",
        "Client Feedback", "Remarks",
    ]
    df = df[cols].dropna(subset=["Pipeline ID"])
    df = df[df["Pipeline ID"].str.startswith("PIP-", na=False)]
    # Drop duplicate Pipeline IDs — keep last (more recent row)
    df = df.drop_duplicates(subset=["Pipeline ID"], keep="last")
    return df.reset_index(drop=True)


def load_clients() -> pd.DataFrame:
    df = pd.read_excel(RECRUITMENT_FILE, sheet_name="MasterData", header=1)
    df.columns = df.iloc[0].tolist()
    df = df.iloc[1:].reset_index(drop=True)
    df = df[["Client ID", "Client Name"]].dropna(subset=["Client ID"])
    df = df[df["Client ID"].str.startswith("CLI-", na=False)]
    return df.reset_index(drop=True)


def load_candidates() -> pd.DataFrame:
    df = pd.read_excel(MANPOWER_FILE, sheet_name="Candidate Database", header=1)
    df.columns = df.iloc[0].tolist()
    df = df.iloc[1:].reset_index(drop=True)
    cols = [
        "Cand ID", "Name", "Entered By", "Phone Number", "Role", "Sub Role",
        "Current Salary", "Expected Salary", "City", "Area (Mumbai)",
        "Gender", "Education Level", "Work Experience", "Source",
        "Candidate Tags", "Binge Screening Remarks", "Notes",
        "CV Link", "Date of Entry", "Interview Date", "Assigned To Client",
    ]
    df = df[cols].dropna(subset=["Cand ID"])
    df = df[df["Cand ID"].str.startswith("CAN-", na=False)]
    return df.reset_index(drop=True)


# ── Main seed ────────────────────────────────────────────────────────────────────


async def seed(mongo_uri: str, db_name: str) -> None:
    from app.modules.brands.models import Brand, Branding
    from app.modules.recruitment.models import (
        ActivityLog,
        Candidate,
        Client,
        Counter,
        Employee,
        Mapping,
        Position,
    )

    # ── Connect ──────────────────────────────────────────────────────────────────
    motor_client = AsyncIOMotorClient(mongo_uri)
    db = motor_client[db_name]
    await init_beanie(
        database=db,
        document_models=[Brand, Employee, Client, Position, Candidate, Mapping, Counter, ActivityLog],
    )
    print(f"Connected to MongoDB: {db.name}")

    # ── Resolve brand ────────────────────────────────────────────────────────────
    brand = await Brand.find_one(Brand.name == BRAND_NAME)
    if not brand:
        print(f"Brand '{BRAND_NAME}' not found. Creating it...")
        brand = Brand(
            owner_id="seed",
            name=BRAND_NAME,
            domain="binge.consulting",
            branding=Branding(),
        )
        await brand.insert()
    brand_id: ObjectId = brand.id
    print(f"Brand: {brand.name}  id={brand_id}")

    # ── Wipe previous seed data scoped to this brand ─────────────────────────────
    print("Clearing previous seed data…")
    await Employee.find(Employee.brand_id == brand_id).delete()
    await Client.find(Client.brand_id == brand_id).delete()
    await Position.find(Position.brand_id == brand_id).delete()
    await Candidate.find(Candidate.brand_id == brand_id).delete()
    await Mapping.find(Mapping.brand_id == brand_id).delete()
    await Counter.find(Counter.brand_id == brand_id).delete()
    await ActivityLog.find(ActivityLog.brand_id == brand_id).delete()
    print("Done.")

    # ── Load Excel data ──────────────────────────────────────────────────────────
    df_clients = load_clients()
    df_positions = load_positions()
    df_pipeline = load_pipeline()
    df_candidates = load_candidates()

    print(f"Loaded: {len(df_clients)} clients, {len(df_positions)} positions, "
          f"{len(df_pipeline)} pipeline entries, {len(df_candidates)} candidates")

    # ── 1. Employees (recruiters) ────────────────────────────────────────────────
    recruiter_names: set[str] = set()
    for col in [df_positions["Assigned To"], df_pipeline["Sourced By"], df_candidates["Entered By"]]:
        for v in col.dropna().unique():
            if isinstance(v, str) and v.strip():
                recruiter_names.add(v.strip())

    employees: dict[str, ObjectId] = {}  # name → _id
    emp_docs: list[Employee] = []
    for name in sorted(recruiter_names):
        oid = ObjectId()
        emp = Employee(
            id=oid,
            brand_id=brand_id,
            name=name,
            email=_fake_email(name, "binge.internal"),
            is_active=True,
        )
        emp_docs.append(emp)
        employees[name] = oid

    if emp_docs:
        await Employee.insert_many(emp_docs)
    print(f"Inserted {len(employees)} employees: {sorted(employees.keys())}")

    # Fallback employee for entries missing a recruiter name
    fallback_emp_id = list(employees.values())[0]

    # ── 2. Clients ───────────────────────────────────────────────────────────────
    clients_by_code: dict[str, ObjectId] = {}   # "CLI-031" → _id
    clients_by_name: dict[str, ObjectId] = {}   # lowercase name → _id
    client_docs: list[Client] = []

    for _, row in df_clients.iterrows():
        code = _clean(row["Client ID"])
        name = _clean(row["Client Name"])
        if not code or not name:
            continue
        oid = ObjectId()
        c = Client(
            id=oid,
            brand_id=brand_id,
            code=code,
            name=name,
            is_active=True,
        )
        client_docs.append(c)
        clients_by_code[code] = oid
        clients_by_name[name.lower()] = oid

    if client_docs:
        await Client.insert_many(client_docs)
    print(f"Inserted {len(client_docs)} clients.")

    # ── 3. Counters ──────────────────────────────────────────────────────────────
    # Track max POS sequence per client from the position data
    pos_seq: dict[str, int] = {}
    for _, row in df_positions.iterrows():
        pos_id = _clean(row["Position ID"]) or ""
        m = re.match(r"(CLI-\d+)-POS-(\d+)", pos_id)
        if m:
            cli_code, seq = m.group(1), int(m.group(2))
            pos_seq[cli_code] = max(pos_seq.get(cli_code, 0), seq)

    counter_docs: list[Counter] = []
    for cli_code, seq in pos_seq.items():
        cli_id = clients_by_code.get(cli_code)
        if not cli_id:
            continue
        counter_docs.append(Counter(id=ObjectId(), brand_id=brand_id, key=f"pos:{cli_code}", seq=seq))

    max_cli = max(
        (int(re.search(r"\d+", c)[0]) for c in clients_by_code if re.search(r"\d+", c)),
        default=0,
    )
    counter_docs.append(Counter(id=ObjectId(), brand_id=brand_id, key="client", seq=max_cli))

    if counter_docs:
        await Counter.insert_many(counter_docs)
    print(f"Inserted {len(counter_docs)} counters.")

    # ── 4. Positions ─────────────────────────────────────────────────────────────
    positions_by_code: dict[str, ObjectId] = {}
    # (client_id, role_lower) → position_id  — used for mapping lookup
    pos_by_client_role: dict[tuple[ObjectId, str], ObjectId] = {}
    # client_id → first position_id  — used as fallback
    pos_by_client_first: dict[ObjectId, ObjectId] = {}
    position_docs: list[Position] = []
    pos_warn = 0

    for _, row in df_positions.iterrows():
        code = _clean(row["Position ID"])
        client_name = _clean(row["Client Name"])
        role = _clean(row["Role"])
        if not code or not role:
            continue

        cli_code = _clean(row["Client ID"])
        cli_id = clients_by_code.get(cli_code) if cli_code else None
        if not cli_id and client_name:
            cli_id = clients_by_name.get(client_name.lower())
        if not cli_id:
            pos_warn += 1
            continue

        assigned_name = _clean(row["Assigned To"])
        assigned_emp_id = employees.get(assigned_name) if assigned_name else None

        total = int(row["No. of Openings"]) if not pd.isna(row["No. of Openings"]) else 0
        filled = int(row["Filled"]) if not pd.isna(row["Filled"]) else 0
        remaining = int(row["Remaining"]) if not pd.isna(row["Remaining"]) else max(0, total - filled)

        oid = ObjectId()
        p = Position(
            id=oid,
            brand_id=brand_id,
            code=code,
            client_id=cli_id,
            client_name=client_name or "",
            role=role,
            department=_clean(row["Department"]),
            city=_clean(row["City"]),
            seniority=_map_seniority(_clean(row["Seniority"])),
            total_seats=total,
            filled_seats=filled,
            remaining_seats=remaining,
            status=_map_status(_clean(row["Status"])),
            assigned_employee_id=assigned_emp_id,
            date_opened=_parse_date(row["Date Opened"]) or datetime.now(UTC),
            target_close=_parse_date(row["Target Close"]),
            notes=_clean(row["Remarks"]),
            is_active=True,
        )
        position_docs.append(p)
        positions_by_code[code] = oid
        pos_by_client_role[(cli_id, role.lower())] = oid
        if cli_id not in pos_by_client_first:
            pos_by_client_first[cli_id] = oid

    if position_docs:
        await Position.insert_many(position_docs)
    if pos_warn:
        print(f"  (skipped {pos_warn} positions — client not resolved)")
    print(f"Inserted {len(position_docs)} positions.")

    # ── 5. Candidates (from Candidate Database) ──────────────────────────────────
    cand_by_excel_id: dict[str, ObjectId] = {}  # "CAN-007" → _id
    cand_by_name: dict[str, ObjectId] = {}       # slug → _id
    candidate_docs: list[Candidate] = []
    seen_emails: set[str] = set()

    for _, row in df_candidates.iterrows():
        cand_id = _clean(row["Cand ID"])
        name = _clean(row["Name"])
        if not cand_id or not name:
            continue

        email = _fake_email(name)
        suffix = 2
        while email in seen_emails:
            email = f"{_slug(name)}{suffix}@binge.internal"
            suffix += 1
        seen_emails.add(email)

        skills: list[str] = []
        role_val = _clean(row["Role"])
        sub_role = _clean(row["Sub Role"])
        if role_val:
            skills.append(role_val.lower())
        if sub_role and sub_role.lower() not in skills:
            skills.append(sub_role.lower())

        oid = ObjectId()
        c = Candidate(
            id=oid,
            brand_id=brand_id,
            full_name=name,
            email=email,
            phone=_clean(row["Phone Number"]),
            experience_years=_exp_years(row["Work Experience"]),
            skills=skills,
            skills_normalized=[s.lower() for s in skills],
            resume_url=_clean(row["CV Link"]),
            current_stage="sourced",
            is_active=True,
            created_at=_parse_date(row["Date of Entry"]) or datetime.now(UTC),
        )
        candidate_docs.append(c)
        cand_by_excel_id[cand_id] = oid
        cand_by_name[_slug(name)] = oid

    if candidate_docs:
        await Candidate.insert_many(candidate_docs)
    print(f"Inserted {len(candidate_docs)} candidates from database.")

    # ── 6. Pipeline-only candidates (no CAN-xxx DB link) ─────────────────────────
    pipeline_only_docs: list[Candidate] = []

    for _, row in df_pipeline.iterrows():
        if _clean(row["DB Cand ID"]):
            continue  # already in candidate DB
        name = _clean(row["Candidate Name"])
        if not name:
            continue
        name_slug = _slug(name)
        if name_slug in cand_by_name:
            continue  # already created (e.g. duplicate pipeline row)

        email = _fake_email(name)
        suffix = 2
        while email in seen_emails:
            email = f"{_slug(name)}{suffix}@binge.internal"
            suffix += 1
        seen_emails.add(email)

        stage_raw = _clean(row["Stage"])
        oid = ObjectId()
        c = Candidate(
            id=oid,
            brand_id=brand_id,
            full_name=name,
            email=email,
            phone=None,
            previous_company=_clean(row["Current Company"]),
            skills=[],
            skills_normalized=[],
            current_stage=_map_stage(stage_raw),
            is_active=True,
            created_at=_parse_date(row["Date Added"]) or datetime.now(UTC),
        )
        pipeline_only_docs.append(c)
        cand_by_name[name_slug] = oid

    if pipeline_only_docs:
        await Candidate.insert_many(pipeline_only_docs)
    print(f"Inserted {len(pipeline_only_docs)} pipeline-only candidates.")

    # ── 7. Mappings ──────────────────────────────────────────────────────────────
    mapping_docs: list[Mapping] = []
    skipped = 0
    now = datetime.now(UTC)

    for _, row in df_pipeline.iterrows():
        pip_id = _clean(row["Pipeline ID"])
        name = _clean(row["Candidate Name"])
        client_name = _clean(row["Client Name"])
        role_raw = _clean(row["Role Applied For"])
        stage_raw = _clean(row["Stage"])
        sourced_by = _clean(row["Sourced By"])

        # Resolve candidate
        db_cand_id = _clean(row["DB Cand ID"])
        cand_oid: ObjectId | None = cand_by_excel_id.get(db_cand_id) if db_cand_id else None
        if not cand_oid and name:
            cand_oid = cand_by_name.get(_slug(name))
        if not cand_oid:
            skipped += 1
            print(f"  SKIP {pip_id}: candidate '{name}' not resolved")
            continue

        # Resolve client
        cli_code = _clean(row["Client ID"])
        cli_oid: ObjectId | None = clients_by_code.get(cli_code) if cli_code else None
        if not cli_oid and client_name:
            cli_oid = clients_by_name.get(client_name.lower())
        if not cli_oid:
            skipped += 1
            print(f"  SKIP {pip_id}: client '{client_name}' not resolved")
            continue

        # Resolve position (exact role → fallback to first position for client)
        pos_oid: ObjectId | None = None
        if role_raw:
            pos_oid = pos_by_client_role.get((cli_oid, role_raw.lower()))
        if not pos_oid:
            pos_oid = pos_by_client_first.get(cli_oid)
        if not pos_oid:
            skipped += 1
            print(f"  SKIP {pip_id}: no position for client '{client_name}'")
            continue

        emp_id = (employees.get(sourced_by) if sourced_by else None) or fallback_emp_id
        stage = _map_stage(stage_raw)
        decision = _map_decision(stage_raw)
        added_at = _parse_date(row["Date Added"]) or now

        m = Mapping(
            id=ObjectId(),
            brand_id=brand_id,
            candidate_id=cand_oid,
            position_id=pos_oid,
            client_id=cli_oid,
            employee_id=emp_id,
            stage=stage,
            decision=decision,
            feedback=_clean(row["Client Feedback"]),
            mapped_at=added_at,
            updated_at=_parse_date(row["Last Updated"]) or added_at,
        )
        mapping_docs.append(m)

    if mapping_docs:
        await Mapping.insert_many(mapping_docs)
    if skipped:
        print(f"  (skipped {skipped} pipeline entries — could not resolve candidate/client/position)")
    print(f"Inserted {len(mapping_docs)} mappings.")

    # ── Summary ──────────────────────────────────────────────────────────────────
    motor_client.close()
    print("\n── Seed complete ──────────────────────────────────────────────────────────")
    print(f"  Employees : {len(employees)}")
    print(f"  Clients   : {len(client_docs)}")
    print(f"  Positions : {len(position_docs)}")
    print(f"  Candidates: {len(candidate_docs) + len(pipeline_only_docs)}")
    print(f"  Mappings  : {len(mapping_docs)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed Excel data into MongoDB")
    parser.add_argument("--uri", help="MongoDB connection URI (overrides .env)")
    parser.add_argument("--db", help="MongoDB database name (overrides .env)")
    args = parser.parse_args()

    uri = args.uri or settings.MONGODB_URI
    db = args.db or settings.MONGODB_DB_NAME

    asyncio.run(seed(mongo_uri=uri, db_name=db))

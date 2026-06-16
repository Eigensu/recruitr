"""Seed real pipeline data from Excel into MongoDB (recruitr DB).

Replaces all mock positions, candidate_mappings, employee_stats,
leaderboard_history, and recruiter_activity with data sourced
directly from the two Excel files.

Usage (from monorepo root):
    python specs/data/seed_real_data.py [--db recruitr] [--dry-run]
"""

from __future__ import annotations

import asyncio
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from app.config import settings

MANPOWER_FILE = Path(__file__).parent / "Binge - Manpower Database - Combined.xlsx"
DASHBOARD_FILE = Path(__file__).parent / "Binge - Recruitment Dashboard (1).xlsx"

COL_CLIENT_NAME = "Client Name"
COL_POSITION_ID = "Position ID"
COL_PIPELINE_ID = "Pipeline ID"
COL_CAND_ID = "Cand ID"

STAGE_MAP = {
    "candidate dropped":    "rejected",
    "rejected":             "rejected",
    "joined":               "position_close",
    "offer accepted":       "offer_accepted",
    "selected":             "offer",
    "sent to client":       "sent_to_client",
    "hold":                 "on_hold",
    "interview scheduled":  "interview",
    "result awaited":       "decision_pending",
}

STAGE_SCORE = {
    "sent_to_client":   10,
    "interview":        20,
    "decision_pending": 25,
    "offer":            30,
    "offer_accepted":   50,
    "position_close":   80,
    "rejected":          5,
    "on_hold":           5,
    "sourced":           2,
}

SENIORITY_MAP = {"junior": "Junior", "mid": "Mid", "senior": "Senior"}


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_date(val) -> datetime | None:
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=UTC) if val.tzinfo is None else val
    try:
        return pd.Timestamp(val).to_pydatetime().replace(tzinfo=UTC)
    except Exception:
        return None


def _str(val, default: str = "") -> str:
    return str(val).strip() if not pd.isna(val) else default


# ── Excel loaders ──────────────────────────────────────────────────────────────

def load_positions_sheet() -> pd.DataFrame:
    df = pd.read_excel(DASHBOARD_FILE, sheet_name="Open Positions", header=1)
    df.columns = df.iloc[0].tolist()
    df = df.iloc[1:].reset_index(drop=True)
    return df[df[COL_POSITION_ID].astype(str).str.startswith("CLI-", na=False)].reset_index(drop=True)


def load_pipeline_sheet() -> pd.DataFrame:
    df = pd.read_excel(DASHBOARD_FILE, sheet_name="Candidate Pipeline", header=1)
    df.columns = df.iloc[0].tolist()
    df = df.iloc[1:].reset_index(drop=True)
    return df[df[COL_PIPELINE_ID].astype(str).str.startswith("PIP-", na=False)].reset_index(drop=True)


def load_candidate_sheet() -> pd.DataFrame:
    df = pd.read_excel(MANPOWER_FILE, sheet_name="Candidate Database", header=1)
    df.columns = df.iloc[0].tolist()
    df = df.iloc[1:].reset_index(drop=True)
    return df[df[COL_CAND_ID].astype(str).str.startswith("CAN-", na=False)].reset_index(drop=True)


# ── Builders ───────────────────────────────────────────────────────────────────

def _position_status(raw: str) -> str:
    if "open" in raw:
        return "open"
    if "clos" in raw:
        return "closed"
    return "on_hold"


def _build_position_doc(
    row: pd.Series,
    brand_id: ObjectId,
    clients_by_code: dict,
    clients_by_name: dict,
    emp_by_firstname: dict,
) -> tuple[dict | None, str, str]:
    """Return (doc, client_code, role_slug) or (None, ...) on skip."""
    pos_id_str = _str(row[COL_POSITION_ID])
    client_name_raw = _str(row[COL_CLIENT_NAME])
    role = _str(row.get("Role", ""))
    client_code = pos_id_str.rsplit("-POS-", 1)[0]

    cl = clients_by_code.get(client_code) or clients_by_name.get(_slug(client_name_raw))
    if not cl:
        return None, client_code, _slug(role)

    total_seats = int(row["No. of Openings"]) if not pd.isna(row.get("No. of Openings")) else 0
    filled = int(row.get("Filled", 0)) if not pd.isna(row.get("Filled", 0)) else 0
    seniority_raw = _str(row.get("Seniority", "mid")).lower()
    status_raw = _str(row.get("Status", "open")).lower()
    date_opened = _parse_date(row.get("Date Opened")) or _now()
    assigned_to = _str(row.get("Assigned To", ""))
    assigned_eid = emp_by_firstname.get(_slug(assigned_to.split()[0])) if assigned_to else None

    doc = {
        "_id": ObjectId(),
        "brand_id": brand_id,
        "code": pos_id_str,
        "client_id": cl["_id"],
        "client_name": cl["name"],
        "role": role,
        "department": _str(row.get("Department", "")) or None,
        "city": _str(row.get("City", "")) or None,
        "seniority": SENIORITY_MAP.get(seniority_raw, "Mid"),
        "requirements": [],
        "total_seats": total_seats,
        "filled_seats": filled,
        "remaining_seats": max(0, total_seats - filled),
        "status": _position_status(status_raw),
        "assigned_employee_id": assigned_eid,
        "date_opened": date_opened,
        "target_close": _parse_date(row.get("Target Close")),
        "notes": _str(row.get("Remarks", "")) or None,
        "is_active": True,
        "created_at": date_opened,
        "updated_at": _now(),
    }
    return doc, client_code, _slug(role)


def _resolve_position(
    client_id_str: str,
    role: str,
    pos_key_to_oid: dict,
) -> ObjectId | None:
    key = f"{client_id_str}||{_slug(role)}"
    if key in pos_key_to_oid:
        return pos_key_to_oid[key]
    return next((v for k, v in pos_key_to_oid.items() if k.startswith(client_id_str + "||")), None)


def _compute_employee_counts(mapping_docs: list[dict]) -> dict[ObjectId, dict]:
    counts: dict[ObjectId, dict] = defaultdict(lambda: {
        "total_mappings": 0, "offers_received": 0,
        "joined_candidates": 0, "rejected_candidates": 0,
        "total_score": 0,
    })
    for m in mapping_docs:
        eid = m["employee_id"]
        stage = m["stage"]
        counts[eid]["total_mappings"] += 1
        counts[eid]["total_score"] += STAGE_SCORE.get(stage, 2)
        if stage in ("offer", "offer_accepted", "position_close"):
            counts[eid]["offers_received"] += 1
        if stage == "position_close":
            counts[eid]["joined_candidates"] += 1
        if stage == "rejected":
            counts[eid]["rejected_candidates"] += 1
    return counts


def _build_stat_docs(ranked: list, now: datetime) -> list[dict]:
    docs = []
    for rank, (eid, counts) in enumerate(ranked, 1):
        xp = counts["total_score"]
        docs.append({
            "_id": ObjectId(),
            "employee_id": eid,
            "mappings": {
                "total_mappings": counts["total_mappings"],
                "offers_received": counts["offers_received"],
                "joined_candidates": counts["joined_candidates"],
                "rejected_candidates": counts["rejected_candidates"],
            },
            "total_score": xp,
            "leaderboard_rank": rank,
            "monthly_growth": 0,
            "xp_points": xp,
            "level": max(1, xp // 100 + 1),
            "streak_days": 0,
            "badges": [],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
    return docs


def _build_lb_docs(ranked: list, month_str: str, now: datetime) -> list[dict]:
    docs = []
    for rank, (eid, counts) in enumerate(ranked, 1):
        total = counts["total_mappings"]
        joined = counts["joined_candidates"]
        docs.append({
            "_id": ObjectId(),
            "employee_id": eid,
            "month": month_str,
            "total_mappings": total,
            "offers_received": counts["offers_received"],
            "joined_candidates": joined,
            "rejected_candidates": counts["rejected_candidates"],
            "success_rate": round(joined / total * 100, 1) if total else 0,
            "monthly_growth": 0,
            "leaderboard_rank": rank,
            "total_score": counts["total_score"],
            "created_at": now,
        })
    return docs


# ── Step functions ─────────────────────────────────────────────────────────────

def _seed_positions(
    brand_id: ObjectId,
    clients_by_code: dict,
    clients_by_name: dict,
    emp_by_firstname: dict,
) -> tuple[list[dict], dict[str, ObjectId]]:
    pos_docs: list[dict] = []
    pos_key_to_oid: dict[str, ObjectId] = {}
    for _, row in load_positions_sheet().iterrows():
        doc, client_code, role_slug = _build_position_doc(
            row, brand_id, clients_by_code, clients_by_name, emp_by_firstname
        )
        if doc is None:
            print(f"  SKIP {_str(row[COL_POSITION_ID])} — client not found: {_str(row[COL_CLIENT_NAME])!r}")
            continue
        pos_docs.append(doc)
        pos_key_to_oid[f"{client_code}||{role_slug}"] = doc["_id"]
        pos_key_to_oid[_str(row[COL_POSITION_ID])] = doc["_id"]
    return pos_docs, pos_key_to_oid


def _resolve_candidate(
    cand_id_str: str,
    cand_name: str,
    cands_by_name: dict,
    can_id_to_name: dict,
) -> ObjectId | None:
    cand_oid: ObjectId | None = None
    if cand_id_str.startswith("CAN-"):
        cand_oid = cands_by_name.get(_slug(can_id_to_name.get(cand_id_str, "")))
    if not cand_oid and cand_name:
        cand_oid = cands_by_name.get(_slug(cand_name))
    return cand_oid


def _seed_mappings(
    brand_id: ObjectId,
    pos_key_to_oid: dict,
    cands_by_name: dict,
    can_id_to_name: dict,
    emp_by_firstname: dict,
) -> tuple[list[dict], dict[ObjectId, str], int]:
    fallback_emp = next(iter(emp_by_firstname.values()))
    mapping_docs: list[dict] = []
    cand_stage_updates: dict[ObjectId, str] = {}
    skipped = 0

    for _, row in load_pipeline_sheet().iterrows():
        pip_id = _str(row[COL_PIPELINE_ID])
        cand_id_str = _str(row.get("DB Cand ID", ""))
        cand_name = _str(row.get("Candidate Name", ""))
        client_id_str = _str(row.get("Client ID", ""))
        role = _str(row.get("Role Applied For", ""))
        stage = STAGE_MAP.get(_str(row.get("Stage", "")).lower(), "sourced")
        sourced_by = _str(row.get("Sourced By", ""))
        date_added = _parse_date(row.get("Date Added")) or _now()

        cand_oid = _resolve_candidate(cand_id_str, cand_name, cands_by_name, can_id_to_name)
        if not cand_oid:
            print(f"  SKIP {pip_id} — candidate not found: {cand_name!r} ({cand_id_str})")
            skipped += 1
            continue

        pos_oid = _resolve_position(client_id_str, role, pos_key_to_oid)
        if not pos_oid:
            print(f"  SKIP {pip_id} — position not found: {client_id_str} / {role!r}")
            skipped += 1
            continue

        emp_oid = (emp_by_firstname.get(_slug(sourced_by.split()[0])) if sourced_by else None) or fallback_emp
        mapping_docs.append({
            "_id": ObjectId(),
            "brand_id": brand_id,
            "candidate_id": cand_oid,
            "position_id": pos_oid,
            "employee_id": emp_oid,
            "stage": stage,
            "history": [{"stage": stage, "at": date_added, "by_employee_id": emp_oid}],
            "mapped_at": date_added,
            "updated_at": date_added,
        })
        cand_stage_updates[cand_oid] = stage

    return mapping_docs, cand_stage_updates, skipped


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _emp_by_firstname(emp_docs: list[dict]) -> dict[str, ObjectId]:
    result: dict[str, ObjectId] = {}
    for e in sorted(emp_docs, key=lambda x: (0 if "binge.internal" in x.get("email", "") else 1)):
        first = _slug(e["name"].split()[0])
        if first not in result:
            result[first] = e["_id"]
    return result


def _print_stat_docs(stat_docs: list[dict], emp_docs: list[dict]) -> None:
    for s in stat_docs:
        name = next((e["name"] for e in emp_docs if e["_id"] == s["employee_id"]), "?")
        m = s["mappings"]
        print(f"  Rank {s['leaderboard_rank']}: {name} — score={s['total_score']}, "
              f"mappings={m['total_mappings']}, joined={m['joined_candidates']}")


async def _write_if_live(db, collection: str, docs: list[dict], dry_run: bool) -> None:
    if dry_run or not docs:
        return
    await db[collection].drop()
    await db[collection].insert_many(docs)


# ── Main ───────────────────────────────────────────────────────────────────────

async def run(mongo_uri: str, db_name: str, dry_run: bool = False) -> None:
    mongo_client = AsyncIOMotorClient(mongo_uri)
    db = mongo_client[db_name]
    tag = "[DRY RUN] " if dry_run else ""
    print(f"{tag}Connected to {db_name}\n")

    brand = await db.brands.find_one({})
    if not brand:
        print("ERROR: No brand found in DB.")
        return
    brand_id: ObjectId = brand["_id"]
    print(f"Brand: {brand.get('name')} ({brand_id})")

    client_docs = await db.clients.find({}, {"_id": 1, "name": 1, "code": 1}).to_list(None)
    clients_by_code = {c["code"]: c for c in client_docs}
    clients_by_name = {_slug(c["name"]): c for c in client_docs}
    print(f"Clients loaded: {len(client_docs)}")

    emp_docs = await db.employees.find({}, {"_id": 1, "name": 1, "email": 1}).to_list(None)
    emp_map = _emp_by_firstname(emp_docs)
    print(f"Employees loaded: {len(emp_docs)}, unique first names: {len(emp_map)}")

    cand_docs = await db.candidates.find({}, {"_id": 1, "full_name": 1}).to_list(None)
    cands_by_name = {_slug(c["full_name"]): c["_id"] for c in cand_docs}
    print(f"Candidates loaded: {len(cand_docs)}\n")

    can_id_to_name: dict[str, str] = {
        _str(row[COL_CAND_ID]): _str(row["Name"])
        for _, row in load_candidate_sheet().iterrows()
    }

    print("=" * 60 + "\nSTEP 1: Seeding Positions\n" + "=" * 60)
    pos_docs, pos_key_to_oid = _seed_positions(brand_id, clients_by_code, clients_by_name, emp_map)
    print(f"Positions to insert: {len(pos_docs)}")
    await _write_if_live(db, "positions", pos_docs, dry_run)
    print("  → Done\n")

    print("=" * 60 + "\nSTEP 2: Seeding Candidate Mappings\n" + "=" * 60)
    mapping_docs, cand_stage_updates, skipped = _seed_mappings(
        brand_id, pos_key_to_oid, cands_by_name, can_id_to_name, emp_map
    )
    print(f"Mappings to insert: {len(mapping_docs)}  |  Skipped: {skipped}")
    await _write_if_live(db, "candidate_mappings", mapping_docs, dry_run)
    if not dry_run:
        for cand_oid, stage in cand_stage_updates.items():
            await db.candidates.update_one({"_id": cand_oid}, {"$set": {"current_stage": stage}})
        print(f"  → Updated current_stage for {len(cand_stage_updates)} candidates")
    print()

    print("=" * 60 + "\nSTEP 3: Computing EmployeeStat\n" + "=" * 60)
    emp_counts = _compute_employee_counts(mapping_docs)
    ranked = sorted(emp_counts.items(), key=lambda x: x[1]["total_score"], reverse=True)
    now = _now()
    stat_docs = _build_stat_docs(ranked, now)
    print(f"EmployeeStat docs: {len(stat_docs)}")
    _print_stat_docs(stat_docs, emp_docs)
    await _write_if_live(db, "employee_stats", stat_docs, dry_run)
    print()

    print("=" * 60 + "\nSTEP 4: Computing LeaderboardHistory\n" + "=" * 60)
    lb_docs = _build_lb_docs(ranked, now.strftime("%Y-%m"), now)
    print(f"LeaderboardHistory docs: {len(lb_docs)}")
    await _write_if_live(db, "leaderboard_history", lb_docs, dry_run)

    if not dry_run:
        await db.recruiter_activity.drop()
        print("\nrecruiter_activity cleared (repopulated by app on future actions)")

    print("\n" + "=" * 60)
    print(f"{tag}DONE")
    print(f"  Positions:           {len(pos_docs)}")
    print(f"  Candidate mappings:  {len(mapping_docs)}  (skipped {skipped})")
    print(f"  EmployeeStat:        {len(stat_docs)}")
    print(f"  LeaderboardHistory:  {len(lb_docs)}")
    print("=" * 60)

    mongo_client.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default=None)
    parser.add_argument("--db", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.uri:
        uri = args.uri
    elif hasattr(settings, "MONGODB_URI_PROD"):
        uri = settings.MONGODB_URI_PROD
    else:
        uri = settings.MONGODB_URI
    db_name = args.db or settings.MONGODB_DB_NAME

    asyncio.run(run(mongo_uri=uri, db_name=db_name, dry_run=args.dry_run))

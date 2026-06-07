"""Upload candidate CVs to Cloudinary and update MongoDB resume_url / resume_public_id.

Usage (from monorepo root):
    python specs/data/upload_cvs.py

Skips files already uploaded (resume_public_id already set on candidate).
Idempotent — safe to re-run.
"""

from __future__ import annotations

import asyncio
import re
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path

import cloudinary
import cloudinary.uploader
import pandas as pd
from beanie import init_beanie
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

PDF_DIR = Path(__file__).parent / "pdfs" / "Database CV_s FY26-27"
MANPOWER_FILE = Path(__file__).parent / "Binge - Manpower Database - Combined.xlsx"

MONGO_URI = "mongodb://localhost:27017/eigensu"
DB_NAME = "eigensu"
BRAND_NAME = "Binge Consulting"
CLOUDINARY_FOLDER = "eigensu/resumes"

# ── Cloudinary config ────────────────────────────────────────────────────────────

def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = ROOT / ".env"
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env

_env = _load_env()

cloudinary.config(
    cloud_name=_env.get("CLOUDINARY_CLOUD_NAME", ""),
    api_key=_env.get("CLOUDINARY_API_KEY", ""),
    api_secret=_env.get("CLOUDINARY_API_SECRET", ""),
    secure=True,
)

# ── Name matching ────────────────────────────────────────────────────────────────

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _build_file_index() -> dict[str, str]:
    """slug(stem) → filename"""
    return {_slug(Path(f.name).stem): f.name for f in PDF_DIR.iterdir() if f.is_file()}


def _match_candidate_to_file(
    cand_id: str,
    name: str,
    cv_hint: str,
    file_index: dict[str, str],
    threshold: float = 0.72,
) -> str | None:
    # 1. Exact CV link match
    if cv_hint and cv_hint != "nan":
        hint_slug = _slug(Path(cv_hint).stem)
        if hint_slug in file_index:
            return file_index[hint_slug]
        for fslug, fname in file_index.items():
            if hint_slug in fslug or fslug in hint_slug:
                return fname

    # 2. Fuzzy name match
    name_slug = _slug(name)
    best_score, best_file = 0.0, None
    for fslug, fname in file_index.items():
        score = SequenceMatcher(None, name_slug, fslug).ratio()
        if score > best_score:
            best_score, best_file = score, fname
    if best_score >= threshold:
        return best_file
    return None


# ── Main ─────────────────────────────────────────────────────────────────────────

SKIP_CANDIDATES = {
    "CAN-479",  # Santanu Bala — SANTANA BHARALI is a different person
}


async def run() -> None:
    from app.modules.brands.models import Brand
    from app.modules.recruitment.models import Candidate

    motor_client = AsyncIOMotorClient(MONGO_URI)
    db = motor_client[DB_NAME]
    await init_beanie(database=db, document_models=[Brand, Candidate])

    brand = await Brand.find_one(Brand.name == BRAND_NAME)
    if not brand:
        print("ERROR: Brand not found.")
        return
    brand_id: ObjectId = brand.id

    # Load candidate name → file mapping from Excel
    df = pd.read_excel(MANPOWER_FILE, sheet_name="Candidate Database", header=1)
    df.columns = df.iloc[0].tolist()
    df = df.iloc[1:].reset_index(drop=True)
    df = df[["Cand ID", "Name", "CV Link"]].dropna(subset=["Cand ID"])
    df = df[df["Cand ID"].str.startswith("CAN-", na=False)].reset_index(drop=True)

    file_index = _build_file_index()

    # Build match map: cand_excel_id → filename
    match_map: dict[str, str] = {}
    for _, row in df.iterrows():
        cid = str(row["Cand ID"]).strip()
        if cid in SKIP_CANDIDATES:
            continue
        name = str(row["Name"]).strip()
        cv_hint = str(row["CV Link"]).strip() if not pd.isna(row["CV Link"]) else ""
        matched_file = _match_candidate_to_file(cid, name, cv_hint, file_index)
        if matched_file:
            match_map[cid] = matched_file

    print(f"Candidates with file matched: {len(match_map)}")

    # Upload each matched file and update MongoDB
    uploaded = skipped_already = skipped_missing = errors = 0

    # Build excel_id → mongo _id map by fetching all candidates for this brand
    all_candidates = await Candidate.find({"brand_id": brand_id}).to_list()

    # We need to match CAN-xxx IDs back to mongo docs.
    # During seed, emails were generated as slug(name)@binge.internal
    # Use full_name slug to correlate
    name_to_oid: dict[str, ObjectId] = {
        re.sub(r"[^a-z0-9]", "", c.full_name.lower()): c.id
        for c in all_candidates
    }
    # Also build from the excel rows: cand_excel_id → candidate name slug
    excel_name_slug: dict[str, str] = {}
    for _, row in df.iterrows():
        cid = str(row["Cand ID"]).strip()
        name = str(row["Name"]).strip()
        excel_name_slug[cid] = re.sub(r"[^a-z0-9]", "", name.lower())

    already_uploaded_names = {
        re.sub(r"[^a-z0-9]", "", c.full_name.lower())
        for c in all_candidates
        if c.resume_public_id
    }

    total = len(match_map)
    for i, (cid, filename) in enumerate(match_map.items(), 1):
        name_slug = excel_name_slug.get(cid, "")
        mongo_oid = name_to_oid.get(name_slug)

        if not mongo_oid:
            print(f"  [{i}/{total}] SKIP {cid} — not found in MongoDB")
            skipped_missing += 1
            continue

        if name_slug in already_uploaded_names:
            skipped_already += 1
            continue

        file_path = PDF_DIR / filename
        if not file_path.exists():
            print(f"  [{i}/{total}] MISSING file: {filename}")
            skipped_missing += 1
            continue

        # Cloudinary public_id: resumes/CAN-001_ajay-dahiya
        public_id = f"resumes/{cid}_{re.sub(r'[^a-z0-9]', '-', name_slug)}"

        try:
            ext = file_path.suffix.lower()
            resource_type = "image" if ext in {".jpg", ".jpeg", ".png"} else "raw"

            result = cloudinary.uploader.upload(
                str(file_path),
                public_id=public_id,
                folder=CLOUDINARY_FOLDER,
                resource_type=resource_type,
                overwrite=False,
                use_filename=False,
            )
            secure_url = result["secure_url"]
            full_public_id = result["public_id"]

            await Candidate.get_motor_collection().update_one(
                {"_id": mongo_oid},
                {"$set": {
                    "resume_url": secure_url,
                    "resume_public_id": full_public_id,
                }},
            )
            uploaded += 1
            print(f"  [{i}/{total}] ✓ {cid} {filename}")

            # Be polite to Cloudinary rate limits
            time.sleep(0.3)

        except Exception as e:
            errors += 1
            print(f"  [{i}/{total}] ERROR {cid} {filename}: {e}")

    motor_client.close()
    print(f"\n── Upload complete ─────────────────────────────────")
    print(f"  Uploaded:         {uploaded}")
    print(f"  Already had URL:  {skipped_already}")
    print(f"  Missing/skipped:  {skipped_missing}")
    print(f"  Errors:           {errors}")


if __name__ == "__main__":
    asyncio.run(run())

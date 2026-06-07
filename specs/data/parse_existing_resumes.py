"""Backfill script — parse resume files for candidates who already have a resume_url.

Finds all candidates with resume_url set but resume_raw_text not yet extracted.
Reads files from local disk first (fast, no auth issues); falls back to HTTP
download for candidates whose file isn't found locally.

Usage (from monorepo root):
    python specs/data/parse_existing_resumes.py

Options (env vars):
    MONGO_URI   — default mongodb://localhost:27017/eigensu
    DRY_RUN=1   — print what would change without writing to DB
    PDF_DIR     — override local PDF search directory
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

import httpx
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.modules.recruitment.models import Candidate
from app.modules.recruitment.utils.resume_parser import parse_resume
from app.modules.storage.service import extract_text_from_pdf

from app.config import settings

DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
PDF_DIR = Path(os.getenv("PDF_DIR", str(Path(__file__).parent / "Database CV_s FY26-27")))


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _build_local_index() -> dict[str, Path]:
    """slug(stem) → full path, for every file in the PDF directory."""
    if not PDF_DIR.exists():
        return {}
    return {_slug(f.stem): f for f in PDF_DIR.iterdir() if f.is_file()}


def _lookup(key: str, local_index: dict[str, Path]) -> Path | None:
    return local_index.get(key) or None


def _public_id_name_part(public_id: str) -> str:
    """Strip CAN-XXX prefix from a public_id stem: "can001ajaydahiya" → "ajaydahiya"."""
    return re.sub(r"^can\d+", "", _slug(Path(public_id).stem))


def _substring_match(name_slug: str, local_index: dict[str, Path]) -> Path | None:
    """Return a file whose slug contains the full name slug (min length 10)."""
    if len(name_slug) < 10:
        return None
    return next((p for fs, p in local_index.items() if name_slug in fs), None)


def _find_local_file(
    name: str,
    public_id: str | None,
    resume_url: str | None,
    local_index: dict[str, Path],
) -> Path | None:
    name_slug = _slug(name)

    return (
        _lookup(name_slug, local_index)
        or (public_id and _lookup(_public_id_name_part(public_id), local_index))
        or (
            resume_url
            and not _is_valid_url(resume_url)
            and _lookup(_slug(Path(resume_url).stem), local_index)
        )
        or _substring_match(name_slug, local_index)
    )


def _is_valid_url(url: str | None) -> bool:
    return bool(url and url.startswith(("http://", "https://")))


async def _get_file_bytes(
    doc: Candidate,
    local_index: dict[str, Path],
    http: httpx.AsyncClient,
) -> tuple[bytes, str]:
    """Return (file_bytes, source_label). Raises on failure."""
    local = _find_local_file(doc.full_name, doc.resume_public_id, doc.resume_url, local_index)
    if local:
        return local.read_bytes(), f"local:{local.name}"

    if not _is_valid_url(doc.resume_url):
        raise ValueError(f"no local file and invalid URL: {doc.resume_url!r}")

    resp = await http.get(doc.resume_url, timeout=30.0)
    resp.raise_for_status()
    return resp.content, "http"


async def process_candidate(
    doc: Candidate,
    local_index: dict[str, Path],
    http: httpx.AsyncClient,
) -> str:
    try:
        file_bytes, source = await _get_file_bytes(doc, local_index, http)
    except Exception as exc:
        return f"  SKIP  {exc}"

    try:
        raw_text = extract_text_from_pdf(file_bytes)
        parsed = parse_resume(raw_text)
    except Exception as exc:
        return f"  SKIP  parse failed ({source}): {exc}"

    update: dict = {"resume_raw_text": raw_text}
    if parsed.skills:
        update["skills"] = parsed.skills
        update["skills_normalized"] = [s.lower() for s in parsed.skills]
    if parsed.phone and not doc.phone:
        update["phone"] = parsed.phone
    if parsed.experience_years is not None and doc.experience_years == 0:
        update["experience_years"] = parsed.experience_years
    if parsed.previous_company and not doc.previous_company:
        update["previous_company"] = parsed.previous_company

    top = ", ".join(parsed.skills[:5]) or "(none)"
    summary = (
        f"  [{source}] skills={len(parsed.skills)}"
        f"  exp={parsed.experience_years}y"
        f"  company={parsed.previous_company!r}"
        f"  top=[{top}]"
    )

    if not DRY_RUN:
        await doc.set(update)

    return summary


async def main(mongo_uri: str) -> None:
    motor = AsyncIOMotorClient(mongo_uri)
    await init_beanie(motor.get_default_database(), document_models=[Candidate])

    query = {"resume_url": {"$ne": None}, "resume_raw_text": None}
    candidates = await Candidate.find(query).to_list()

    if not candidates:
        print("No candidates need parsing.")
        return

    local_index = _build_local_index()
    mode = "[DRY RUN] " if DRY_RUN else ""
    print(f"{mode}Found {len(candidates)} candidate(s).  Local PDF dir: {PDF_DIR} ({len(local_index)} files)\n")

    ok = skipped = 0
    async with httpx.AsyncClient() as http:
        for i, doc in enumerate(candidates, 1):
            print(f"[{i}/{len(candidates)}] {doc.full_name} ({doc.id})")
            result = await process_candidate(doc, local_index, http)
            print(result)
            if result.startswith("  SKIP"):
                skipped += 1
            else:
                ok += 1

    print(f"\nDone.  Parsed: {ok}  Skipped: {skipped}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill parsed resume text")
    parser.add_argument("--uri", help="MongoDB connection URI (overrides .env)")
    args = parser.parse_args()

    uri = args.uri or settings.MONGODB_URI
    asyncio.run(main(mongo_uri=uri))

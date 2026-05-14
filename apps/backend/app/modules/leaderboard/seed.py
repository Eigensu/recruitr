"""Seed utility for leaderboard collections with realistic demo data."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from pymongo import AsyncMongoClient

from app.config import settings
from app.database import init_db
from app.modules.dashboard.enums import JobStatus, PipelineStage
from app.modules.leaderboard.enums import ActivityTypeEnum, BadgeRarityEnum, BadgeTypeEnum
from app.modules.leaderboard.models import LeaderboardMappings
from app.modules.leaderboard.repository.writes import recompute_ranks
from app.modules.leaderboard.utils.badge_engine import evaluate_badges
from app.modules.leaderboard.utils.growth_calculator import success_rate
from app.modules.leaderboard.utils.ranking_calculator import calculate_score

RECRUITERS = [
    ("Manokamna Rao", "manokamna@binge.jobs", 67, 24, 19, 8, 34),
    ("Hardik Patel", "hardik@binge.jobs", 58, 20, 16, 11, 28),
    ("Edwin D'Souza", "edwin@binge.jobs", 54, 19, 15, 9, 22),
    ("Riya Chatterjee", "riya@binge.jobs", 48, 16, 12, 13, 18),
    ("Aakash Menon", "aakash@binge.jobs", 43, 14, 10, 10, 15),
    ("Tanvi Kulkarni", "tanvi@binge.jobs", 38, 12, 9, 8, 24),
    ("Nikhil Bhat", "nikhil@binge.jobs", 32, 10, 7, 12, 11),
    ("Arjun Iyer", "arjun@binge.jobs", 28, 8, 6, 9, 52),
    ("Priya Nair", "priya@binge.jobs", 24, 7, 5, 7, 9),
    ("Mohit Sharma", "mohit@binge.jobs", 20, 6, 4, 8, 7),
]

BADGES = [
    (BadgeTypeEnum.TOP_MAPPER, "Top Mapper", "Mapped 100+ candidates this month", "🗺️", BadgeRarityEnum.EPIC, 300, "total_mappings", 100),
    (BadgeTypeEnum.HIRING_CHAMPION, "Hiring Champion", "Closed 25 successful joins", "🏆", BadgeRarityEnum.LEGENDARY, 500, "joined_candidates", 25),
    (BadgeTypeEnum.OFFER_KING, "Offer King", "Generated 50 offers in one cycle", "👑", BadgeRarityEnum.LEGENDARY, 450, "offers_received", 50),
    (BadgeTypeEnum.CONSISTENCY_STAR, "Consistency Star", "Maintained a 30-day streak", "⭐", BadgeRarityEnum.RARE, 250, "streak_days", 30),
    (BadgeTypeEnum.RISING_RECRUITER, "Rising Recruiter", "Reached 20% month-over-month growth", "🚀", BadgeRarityEnum.COMMON, 150, "monthly_growth", 20),
    (BadgeTypeEnum.FAST_CLOSER, "Fast Closer", "Closed 10 joins during a strong streak", "⚡", BadgeRarityEnum.RARE, 275, "fast_close", 10),
    (BadgeTypeEnum.ELITE_RECRUITER, "Elite Recruiter", "Top-tier recruiter across all metrics", "💎", BadgeRarityEnum.LEGENDARY, 650, "score", 900),
    (BadgeTypeEnum.RECRUITMENT_NINJA, "Recruitment Ninja", "High joins with minimal rejections", "🥷", BadgeRarityEnum.EPIC, 325, "join_quality", 10),
]

COMPANIES = [
    ("August Cafe", "Restaurant Manager", 8, 6),
    ("Olive", "Sous Chef", 5, 5),
    ("Aures Hospitality", "Commis Chef", 12, 7),
    ("Ghost Kitchens", "Kitchen Assistant", 10, 4),
    ("Hunger Inc", "Captain", 6, 3),
    ("Le 15", "Pastry Chef", 4, 4),
    ("NOTO", "Bartender", 7, 2),
]


async def seed_leaderboard() -> None:
    await init_db()
    async with AsyncMongoClient(settings.MONGODB_URI) as client:
        db = client[settings.MONGODB_DB_NAME]

        employees_col = db["employees"]
        stats_col = db["employee_stats"]
        history_col = db["leaderboard_history"]
        badges_col = db["badges"]
        activity_col = db["recruiter_activity"]
        candidates_col = db["candidates"]
        mappings_col = db["candidate_mappings"]
        jobs_col = db["job_openings"]

        for badge in BADGES:
            name, label, description, icon, rarity, xp_reward, condition_type, condition_value = badge
            await badges_col.update_one(
                {"name": name.value},
                {
                    "$set": {
                        "name": name.value,
                        "label": label,
                        "description": description,
                        "icon": icon,
                        "rarity": rarity.value,
                        "xp_reward": xp_reward,
                        "condition_type": condition_type,
                        "condition_value": condition_value,
                        "created_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )

        employees: list[dict] = []
        for idx, (name, email, mappings, offers, joined, rejected, growth) in enumerate(RECRUITERS):
            await employees_col.update_one(
                {"email": email},
                {
                    "$setOnInsert": {
                        "name": name,
                        "email": email,
                        "created_at": datetime.now(timezone.utc) - timedelta(days=120 + idx * 3),
                        "updated_at": datetime.now(timezone.utc),
                        "is_active": True,
                    }
                },
                upsert=True,
            )
            employee = await employees_col.find_one({"email": email})
            if employee is None:
                continue
            employees.append(employee)
            score = calculate_score(joined_candidates=joined, offers_received=offers, total_mappings=mappings, rejected_candidates=rejected)
            stat = {
                "employee_id": employee["_id"],
                "mappings": LeaderboardMappings(total_mappings=mappings, offers_received=offers, joined_candidates=joined, rejected_candidates=rejected).model_dump(),
                "total_score": score,
                "leaderboard_rank": idx + 1,
                "monthly_growth": growth,
                "xp_points": score,
                "level": max(1, score // 500 + 1),
                "streak_days": 35 - idx,
                "badges": [badge.value for badge in evaluate_badges({"mappings": {"total_mappings": mappings, "offers_received": offers, "joined_candidates": joined, "rejected_candidates": rejected}, "monthly_growth": growth, "streak_days": 35 - idx, "total_score": score})],
                "is_active": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            await stats_col.update_one({"employee_id": employee["_id"]}, {"$set": stat}, upsert=True)

        months = ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05"]
        for idx, employee in enumerate(employees):
            base = RECRUITERS[idx]
            mappings, offers, joined, rejected, _growth = base[2], base[3], base[4], base[5], base[6]
            for month_idx, month in enumerate(months):
                factor = (month_idx + 1) / len(months)
                total = max(1, round(mappings * factor))
                off = round(offers * factor)
                join = round(joined * factor)
                rej = round(rejected * factor)
                await history_col.update_one(
                    {"employee_id": employee["_id"], "month": month},
                    {
                        "$set": {
                            "employee_id": employee["_id"],
                            "month": month,
                            "total_mappings": total,
                            "offers_received": off,
                            "joined_candidates": join,
                            "rejected_candidates": rej,
                            "success_rate": success_rate(join, off),
                            "monthly_growth": 0 if month_idx == 0 else round(((total - max(1, round(mappings * (month_idx / len(months))))) / max(1, round(mappings * (month_idx / len(months))))) * 100, 2),
                            "leaderboard_rank": idx + 1,
                            "total_score": calculate_score(joined_candidates=join, offers_received=off, total_mappings=total, rejected_candidates=rej),
                            "created_at": datetime.now(timezone.utc),
                        }
                    },
                    upsert=True,
                )

        job_docs = []
        for company, role, seats, filled in COMPANIES:
            await jobs_col.update_one(
                {"client_name": company, "role": role},
                {
                    "$setOnInsert": {
                        "client_name": company,
                        "role": role,
                        "total_seats": seats,
                        "filled_seats": filled,
                        "remaining_seats": max(seats - filled, 0),
                        "status": JobStatus.open.value,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                        "is_active": True,
                    }
                },
                upsert=True,
            )
            job = await jobs_col.find_one({"client_name": company, "role": role})
            if job is None:
                continue
            job_docs.append(job)

        candidate_docs = []
        for idx in range(36):
            await candidates_col.update_one(
                {"email": f"candidate{idx + 1}@example.com"},
                {
                    "$setOnInsert": {
                        "full_name": f"Candidate {idx + 1}",
                        "email": f"candidate{idx + 1}@example.com",
                        "current_stage": PipelineStage.added.value,
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                        "is_active": True,
                    }
                },
                upsert=True,
            )
            candidate = await candidates_col.find_one({"email": f"candidate{idx + 1}@example.com"})
            if candidate is None:
                continue
            candidate_docs.append(candidate)

        mapping_docs = []
        for idx, candidate in enumerate(candidate_docs):
            employee = employees[idx % len(employees)]
            job = job_docs[idx % len(job_docs)]
            stage = PipelineStage.joined.value if idx % 4 == 0 else PipelineStage.offer_sent.value
            await mappings_col.update_one(
                {"candidate_id": candidate["_id"], "job_opening_id": job["_id"]},
                {
                    "$set": {
                        "employee_id": employee["_id"],
                        "candidate_id": candidate["_id"],
                        "job_opening_id": job["_id"],
                        "pipeline_stage": stage,
                        "mapped_at": datetime.now(timezone.utc) - timedelta(days=idx),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
            mapping_docs.append((employee, candidate, job, stage))

        for idx, (employee, candidate, job, _stage) in enumerate(mapping_docs[:18]):
            activity_type = [ActivityTypeEnum.CANDIDATE_JOINED, ActivityTypeEnum.OFFER_RECEIVED, ActivityTypeEnum.MAPPING_COMPLETED, ActivityTypeEnum.CANDIDATE_REJECTED][idx % 4]
            await activity_col.update_one(
                {"activity_reference_id": f"seed-{employee['_id']}-{candidate['_id']}-{activity_type.value}"},
                {
                    "$set": {
                        "employee_id": employee["_id"],
                        "candidate_id": candidate["_id"],
                        "activity_type": activity_type.value,
                        "title": activity_type.value.replace("_", " ").title(),
                        "description": f"{candidate['full_name']} → {job['client_name']} ({job['role']})",
                        "points_earned": 15 if activity_type == ActivityTypeEnum.CANDIDATE_JOINED else 8,
                        "activity_reference_id": f"seed-{employee['_id']}-{candidate['_id']}-{activity_type.value}",
                        "created_at": datetime.now(timezone.utc) - timedelta(minutes=idx * 18),
                    }
                },
                upsert=True,
            )

        await recompute_ranks()
    print("Leaderboard seed complete")


if __name__ == "__main__":
    asyncio.run(seed_leaderboard())
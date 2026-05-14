"""Atomic MongoDB writes and maintenance for leaderboard."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.common.utils.object_id import to_object_id
from app.modules.leaderboard.enums import ActivityTypeEnum
from app.modules.leaderboard.models import Badge, EmployeeStat, LeaderboardHistory, RecruiterActivity
from app.modules.leaderboard.utils.badge_engine import evaluate_badges
from app.modules.leaderboard.utils.cache_manager import update_rank
from app.modules.leaderboard.utils.growth_calculator import percent_growth, success_rate
from app.modules.leaderboard.utils.ranking_calculator import activity_points, calculate_score


async def record_activity_atomic(
    *,
    employee_id: str,
    candidate_id: str | None,
    activity_type: ActivityTypeEnum,
    activity_reference_id: str,
    title: str,
    description: str,
) -> bool:
    employee_oid = to_object_id(employee_id, "employee_id")
    candidate_oid = to_object_id(candidate_id, "candidate_id") if candidate_id else None
    if employee_oid is None:
        return False

    points = activity_points(activity_type)
    try:
        await RecruiterActivity.get_motor_collection().insert_one(
            {
                "employee_id": employee_oid,
                "candidate_id": candidate_oid,
                "activity_type": activity_type.value,
                "title": title,
                "description": description,
                "points_earned": points,
                "activity_reference_id": activity_reference_id,
                "created_at": datetime.utcnow(),
            }
        )
    except DuplicateKeyError:
        return False

    inc: dict[str, int] = {"xp_points": max(points, 0)}
    if activity_type == ActivityTypeEnum.MAPPING_COMPLETED:
        inc["mappings.total_mappings"] = 1
    elif activity_type == ActivityTypeEnum.OFFER_RECEIVED:
        inc["mappings.offers_received"] = 1
    elif activity_type == ActivityTypeEnum.CANDIDATE_JOINED:
        inc["mappings.joined_candidates"] = 1
    elif activity_type == ActivityTypeEnum.CANDIDATE_REJECTED:
        inc["mappings.rejected_candidates"] = 1

    await EmployeeStat.get_motor_collection().update_one(
        {"employee_id": employee_oid},
        {
            "$inc": inc,
            "$set": {"updated_at": datetime.utcnow(), "is_active": True},
            "$setOnInsert": {"created_at": datetime.utcnow(), "employee_id": employee_oid, "level": 1, "streak_days": 0},
        },
        upsert=True,
    )

    await recompute_ranks()
    stat = await EmployeeStat.get_motor_collection().find_one({"employee_id": employee_oid})
    if stat:
        await unlock_badges(employee_oid, evaluate_badges(stat))
    return True


async def recompute_ranks() -> list[dict[str, Any]]:
    stats = await EmployeeStat.get_motor_collection().find({"is_active": True}).sort("total_score", -1).to_list(length=None)
    results: list[dict[str, Any]] = []
    for index, stat in enumerate(stats, start=1):
        score = int(stat.get("xp_points") or stat.get("total_score", 0))
        await EmployeeStat.get_motor_collection().update_one(
            {"_id": stat["_id"]},
            {"$set": {"leaderboard_rank": index, "total_score": score, "xp_points": score, "updated_at": datetime.utcnow()}},
        )
        await update_rank(str(stat["employee_id"]), score)
        results.append({"employee_id": str(stat["employee_id"]), "score": score, "rank": index})
    return results


async def unlock_badges(employee_oid: Any, badges: list) -> None:
    if not badges:
        return
    await EmployeeStat.get_motor_collection().update_one(
        {"employee_id": employee_oid},
        {"$addToSet": {"badges": {"$each": [badge.value for badge in badges]}}, "$set": {"updated_at": datetime.utcnow()}},
    )


async def create_monthly_snapshots(month: str) -> int:
    stats = await EmployeeStat.get_motor_collection().find({"is_active": True}).to_list(length=None)
    for stat in stats:
        previous_cursor = await LeaderboardHistory.get_motor_collection().find({"employee_id": stat["employee_id"], "month": {"$lt": month}}).sort("month", -1).limit(1)
        previous = await previous_cursor.to_list(length=None)
        previous_total = int(previous[0]["total_mappings"]) if previous else 0
        mappings = stat.get("mappings", {})
        growth = percent_growth(int(mappings.get("total_mappings", 0)), previous_total)
        await LeaderboardHistory.get_motor_collection().update_one(
            {"employee_id": stat["employee_id"], "month": month},
            {
                "$set": {
                    "employee_id": stat["employee_id"],
                    "month": month,
                    "total_mappings": int(mappings.get("total_mappings", 0)),
                    "offers_received": int(mappings.get("offers_received", 0)),
                    "joined_candidates": int(mappings.get("joined_candidates", 0)),
                    "rejected_candidates": int(mappings.get("rejected_candidates", 0)),
                    "success_rate": success_rate(int(mappings.get("joined_candidates", 0)), int(mappings.get("offers_received", 0))),
                    "monthly_growth": growth,
                    "leaderboard_rank": int(stat.get("leaderboard_rank", 0)),
                    "total_score": int(stat.get("total_score", 0)),
                    "created_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )
    return len(stats)
"""Atomic MongoDB writes and maintenance for leaderboard."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.common.utils.object_id import to_object_id
from app.modules.leaderboard.enums import ActivityTypeEnum
from app.modules.leaderboard.models import EmployeeStat, LeaderboardHistory, RecruiterActivity
from app.modules.leaderboard.utils.badge_engine import evaluate_badges
from app.modules.leaderboard.utils.cache_manager import update_rank
from app.modules.leaderboard.utils.growth_calculator import percent_growth, success_rate
from app.modules.leaderboard.utils.ranking_calculator import activity_points


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
    if candidate_id and candidate_oid is None:
        return False

    points = activity_points(activity_type)
    inc: dict[str, int] = {"xp_points": points, "total_score": points}
    if activity_type == ActivityTypeEnum.MAPPING_COMPLETED:
        inc["mappings.total_mappings"] = 1
    elif activity_type == ActivityTypeEnum.OFFER_RECEIVED:
        inc["mappings.offers_received"] = 1
    elif activity_type == ActivityTypeEnum.CANDIDATE_JOINED:
        inc["mappings.joined_candidates"] = 1
    elif activity_type == ActivityTypeEnum.CANDIDATE_REJECTED:
        inc["mappings.rejected_candidates"] = 1

    client = RecruiterActivity.get_motor_collection().database.client
    async with await client.start_session() as session, session.start_transaction():
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
                    "created_at": datetime.now(UTC),
                },
                session=session,
            )
        except DuplicateKeyError:
            await session.abort_transaction()
            return False

        await EmployeeStat.get_motor_collection().update_one(
            {"employee_id": employee_oid},
            {
                "$inc": inc,
                "$set": {"updated_at": datetime.now(UTC), "is_active": True},
                "$setOnInsert": {
                    "created_at": datetime.now(UTC),
                    "employee_id": employee_oid,
                    "level": 1,
                    "streak_days": 0,
                },
            },
            upsert=True,
            session=session,
        )

    stat = await EmployeeStat.get_motor_collection().find_one({"employee_id": employee_oid})
    if stat:
        score = int(stat.get("xp_points", stat.get("total_score", 0)))
        await update_rank(str(employee_oid), score)
        await unlock_badges(employee_oid, evaluate_badges(stat))
    return True


async def recompute_ranks() -> list[dict[str, Any]]:
    stats = await EmployeeStat.get_motor_collection().find({"is_active": True}).to_list(length=None)
    refreshed: list[dict[str, Any]] = []
    for stat in stats:
        score = int(stat.get("xp_points", stat.get("total_score", 0)))
        await EmployeeStat.get_motor_collection().update_one(
            {"_id": stat["_id"]},
            {"$set": {"total_score": score, "xp_points": score, "updated_at": datetime.now(UTC)}},
        )
        await update_rank(str(stat["employee_id"]), score)
        refreshed.append(
            {"_id": stat["_id"], "employee_id": str(stat["employee_id"]), "score": score}
        )
    refreshed.sort(key=lambda item: (-item["score"], item["employee_id"]))
    results: list[dict[str, Any]] = []
    for index, stat in enumerate(refreshed, start=1):
        await EmployeeStat.get_motor_collection().update_one(
            {"_id": stat["_id"]},
            {"$set": {"leaderboard_rank": index, "updated_at": datetime.now(UTC)}},
        )
        results.append({"employee_id": stat["employee_id"], "score": stat["score"], "rank": index})
    return results


async def unlock_badges(employee_oid: Any, badges: list) -> None:
    if not badges:
        return
    await EmployeeStat.get_motor_collection().update_one(
        {"employee_id": employee_oid},
        {
            "$addToSet": {"badges": {"$each": [badge.value for badge in badges]}},
            "$set": {"updated_at": datetime.now(UTC)},
        },
    )


async def create_monthly_snapshots(month: str) -> int:
    stats = await EmployeeStat.get_motor_collection().find({"is_active": True}).to_list(length=None)
    for stat in stats:
        previous_cursor = (
            LeaderboardHistory.get_motor_collection()
            .find({"employee_id": stat["employee_id"], "month": {"$lt": month}})
            .sort("month", -1)
            .limit(1)
        )
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
                    "success_rate": success_rate(
                        int(mappings.get("joined_candidates", 0)),
                        int(mappings.get("offers_received", 0)),
                    ),
                    "monthly_growth": growth,
                    "leaderboard_rank": int(stat.get("leaderboard_rank", 0)),
                    "total_score": int(stat.get("total_score", 0)),
                },
                "$setOnInsert": {
                    "created_at": datetime.now(UTC),
                },
            },
            upsert=True,
        )
    return len(stats)

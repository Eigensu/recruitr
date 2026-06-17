"""MongoDB aggregation layer for leaderboard reads."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from app.common.utils.object_id import to_object_id
from app.modules.dashboard.models import CandidateMapping, DashboardEmployee, JobOpening
from app.modules.leaderboard.enums import ActivityTypeEnum, BadgeTypeEnum
from app.modules.leaderboard.models import (
    Badge,
    EmployeeStat,
    LeaderboardHistory,
    RecruiterActivity,
)
from app.modules.leaderboard.utils.cache_manager import rankings_count, rankings_window
from app.modules.leaderboard.utils.growth_calculator import success_rate

AVATAR_COLORS = [
    "#F3FF54",
    "#3DDC97",
    "#60A5FA",
    "#F7C948",
    "#FB923C",
    "#C084FC",
    "#2DD4BF",
    "#FF8A8A",
]


def _initials(name: str) -> str:
    return "".join(part[:1] for part in name.split()[:2]).upper() or "NA"


def _month_label(month: str) -> str:
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%b")
    except ValueError:
        return month


def _tone(activity_type: str) -> str:
    return {
        ActivityTypeEnum.CANDIDATE_JOINED.value: "green",
        ActivityTypeEnum.OFFER_RECEIVED.value: "yellow",
        ActivityTypeEnum.CANDIDATE_REJECTED.value: "red",
        ActivityTypeEnum.BADGE_UNLOCKED.value: "yellow",
        ActivityTypeEnum.RANK_INCREASED.value: "green",
    }.get(activity_type, "neutral")


def _badge_color(badge: BadgeTypeEnum, rank: int) -> str:
    if badge in {
        BadgeTypeEnum.ELITE_RECRUITER,
        BadgeTypeEnum.HIRING_CHAMPION,
        BadgeTypeEnum.OFFER_KING,
    }:
        return AVATAR_COLORS[0]
    return AVATAR_COLORS[rank % len(AVATAR_COLORS)]


async def _hydrate_employee_stats(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    employee_ids = [item["employee_id"] for item in items]
    employees = (
        await DashboardEmployee.get_motor_collection()
        .find({"_id": {"$in": employee_ids}, **_RECRUITER_ONLY})
        .to_list(length=None)
    )
    employees_by_id = {employee["_id"]: employee for employee in employees}
    monthly = await _monthly_totals_for_employees(employee_ids)

    hydrated: list[dict[str, Any]] = []
    for item in items:
        employee = employees_by_id.get(item["employee_id"])
        if employee is None:
            continue
        badges = list(item.get("badges") or [])
        badge = badges[0] if badges else BadgeTypeEnum.RISING_RECRUITER
        mappings = item.get("mappings", {})
        hydrated.append(
            {
                "id": str(employee["_id"]),
                "name": employee["name"],
                "email": employee["email"],
                "initials": _initials(employee["name"]),
                "rank": int(item.get("leaderboard_rank", 0)),
                "xp": int(item.get("xp_points") or item.get("total_score", 0)),
                "level": int(item.get("level", 1)),
                "totalMappings": int(mappings.get("total_mappings", 0)),
                "offersReceived": int(mappings.get("offers_received", 0)),
                "joined": int(mappings.get("joined_candidates", 0)),
                "rejected": int(mappings.get("rejected_candidates", 0)),
                "monthlyGrowth": float(item.get("monthly_growth", 0)),
                "successRate": success_rate(
                    int(mappings.get("joined_candidates", 0)),
                    int(mappings.get("offers_received", 0)),
                ),
                "badge": badge,
                "badges": badges,
                "monthlyData": monthly.get(str(employee["_id"]), [0, 0, 0, 0, 0, 0]),
                "avatarColor": _badge_color(badge, int(item.get("leaderboard_rank", 0))),
            }
        )
    return hydrated


async def _monthly_totals_for_employees(employee_ids: list[Any]) -> dict[str, list[int]]:
    if not employee_ids:
        return {}
    rows = (
        await LeaderboardHistory.get_motor_collection()
        .find({"employee_id": {"$in": employee_ids}})
        .sort("month")
        .to_list(length=None)
    )
    month_labels = sorted({row["month"] for row in rows})[-6:]
    out: dict[str, list[int]] = {str(employee_id): [0] * 6 for employee_id in employee_ids}
    start = max(0, 6 - len(month_labels))
    for row in rows:
        if row["month"] in month_labels:
            out[str(row["employee_id"])][start + month_labels.index(row["month"])] = int(
                row["total_mappings"]
            )
    return out


async def fetch_rankings(
    *, page: int, limit: int, search: str | None, sort_by: str, month: str | None
) -> dict[str, Any]:
    if month:
        pipeline: list[dict[str, Any]] = [
            {"$match": {"month": month}},
            {
                "$lookup": {
                    "from": "employees",
                    "localField": "employee_id",
                    "foreignField": "_id",
                    "as": "employee",
                }
            },
            {"$unwind": "$employee"},
            {
                "$match": {
                    "employee.is_active": True,
                    "employee.role": {"$nin": ["admin", "maintainer"]},
                }
            },
        ]
        if search:
            escaped_search = re.escape(search)
            pipeline.append(
                {"$match": {"employee.name": {"$regex": escaped_search, "$options": "i"}}}
            )
        sort = (
            {"leaderboard_rank": 1, "total_score": -1} if sort_by == "rank" else {"total_score": -1}
        )
        pipeline.extend(
            [
                {"$sort": sort},
                {
                    "$facet": {
                        "items": [{"$skip": (page - 1) * limit}, {"$limit": limit}],
                        "total": [{"$count": "count"}],
                    }
                },
            ]
        )
        cursor = await LeaderboardHistory.get_motor_collection().aggregate(pipeline)  # type: ignore
        result = await cursor.to_list(length=None)
        payload = result[0] if result else {"items": [], "total": []}
        items = payload.get("items", [])
        hydrated = []
        monthly = await _monthly_totals_for_employees([item["employee_id"] for item in items])
        for item in items:
            employee = item["employee"]
            badges = list(item.get("badges") or [])
            badge = badges[0] if badges else BadgeTypeEnum.RISING_RECRUITER
            mappings = {
                "total_mappings": int(item.get("total_mappings", 0)),
                "offers_received": int(item.get("offers_received", 0)),
                "joined_candidates": int(item.get("joined_candidates", 0)),
                "rejected_candidates": int(item.get("rejected_candidates", 0)),
            }
            hydrated.append(
                {
                    "id": str(employee["_id"]),
                    "name": employee["name"],
                    "email": employee["email"],
                    "initials": _initials(employee["name"]),
                    "rank": int(item.get("leaderboard_rank", 0)),
                    "xp": int(item.get("total_score", 0)),
                    "level": int(item.get("level", 1)),
                    "totalMappings": mappings["total_mappings"],
                    "offersReceived": mappings["offers_received"],
                    "joined": mappings["joined_candidates"],
                    "rejected": mappings["rejected_candidates"],
                    "monthlyGrowth": float(item.get("monthly_growth", 0)),
                    "successRate": success_rate(
                        mappings["joined_candidates"], mappings["offers_received"]
                    ),
                    "badge": badge,
                    "badges": badges,
                    "monthlyData": monthly.get(str(employee["_id"]), [0, 0, 0, 0, 0, 0]),
                    "avatarColor": _badge_color(badge, int(item.get("leaderboard_rank", 0))),
                }
            )
        return {
            "items": hydrated,
            "total": int(payload.get("total", [{}])[0].get("count", 0))
            if payload.get("total")
            else 0,
            "page": page,
            "limit": limit,
        }

    base_query: dict[str, Any] = {"is_active": True}

    if sort_by in {"rank", "score"} and not search:
        total = await rankings_count()
        ids = await rankings_window(page, limit)
        if ids:
            employee_object_ids = [to_object_id(employee_id, "employee_id") for employee_id in ids]
            employee_object_ids = [
                employee_id for employee_id in employee_object_ids if employee_id is not None
            ]
            stats = (
                await EmployeeStat.get_motor_collection()
                .find({"employee_id": {"$in": employee_object_ids}})
                .to_list(length=None)
            )
            stats_by_employee = {str(stat["employee_id"]): stat for stat in stats}
            ordered = []
            for employee_id in ids:
                stat = stats_by_employee.get(employee_id)
                if stat is None:
                    continue
                ordered.append(stat)
            hydrated = await _hydrate_employee_stats(ordered)
            return {"items": hydrated, "total": total, "page": page, "limit": limit}

    pipeline = [
        {"$match": base_query},
        {
            "$lookup": {
                "from": "employees",
                "localField": "employee_id",
                "foreignField": "_id",
                "as": "employee",
            }
        },
        {"$unwind": "$employee"},
        {"$match": {"employee.is_active": True}},
    ]
    if search:
        escaped_search = re.escape(search)
        pipeline.append({"$match": {"employee.name": {"$regex": escaped_search, "$options": "i"}}})
    sort = {"leaderboard_rank": 1, "total_score": -1} if sort_by == "rank" else {"total_score": -1}
    if sort_by == "monthly_growth":
        sort = {"monthly_growth": -1, "total_score": -1}
    pipeline.extend(
        [
            {"$sort": sort},
            {
                "$facet": {
                    "items": [{"$skip": (page - 1) * limit}, {"$limit": limit}],
                    "total": [{"$count": "count"}],
                }
            },
        ]
    )
    cursor = await EmployeeStat.get_motor_collection().aggregate(pipeline)  # type: ignore
    result = await cursor.to_list(length=None)
    payload = result[0] if result else {"items": [], "total": []}
    items = payload.get("items", [])
    hydrated = await _hydrate_employee_stats(items)
    return {
        "items": hydrated,
        "total": int(payload.get("total", [{}])[0].get("count", 0)) if payload.get("total") else 0,
        "page": page,
        "limit": limit,
    }


async def fetch_overview() -> dict[str, Any]:
    stats = await EmployeeStat.find(EmployeeStat.is_active == True).to_list()  # noqa: E712
    job_count = await JobOpening.get_motor_collection().count_documents({"is_active": True})
    total_recruiters = len(stats)
    total_mappings = sum(stat.mappings.total_mappings for stat in stats)
    offers = sum(stat.mappings.offers_received for stat in stats)
    joins = sum(stat.mappings.joined_candidates for stat in stats)
    growth = (
        round(sum(stat.monthly_growth for stat in stats) / total_recruiters, 2)
        if total_recruiters
        else 0.0
    )
    top_score = max((stat.xp_points or stat.total_score for stat in stats), default=0)
    top_stat = max(stats, key=lambda stat: stat.xp_points or stat.total_score, default=None)
    recruiter = None
    if top_stat is not None:
        recruiter_data = await _hydrate_employee_stats(
            [top_stat.model_dump() | {"employee_id": top_stat.employee_id}]
        )
        recruiter = recruiter_data[0] if recruiter_data else None
    return {
        "summary": {
            "recruiters": total_recruiters,
            "mappings": total_mappings,
            "offers": offers,
            "joins": joins,
            "growth": growth,
            "top_score": top_score,
            "companies": job_count,
        },
        "top_recruiter": recruiter,
    }


async def fetch_recruiter(employee_id: str) -> dict[str, Any] | None:
    oid = to_object_id(employee_id, "employee_id")
    if oid is None:
        return None
    stat = await EmployeeStat.find_one(EmployeeStat.employee_id == oid)
    employee = await DashboardEmployee.get(oid)
    if stat is None or employee is None:
        return None
    items = await _hydrate_employee_stats([stat.model_dump() | {"employee_id": stat.employee_id}])
    if not items:
        return None
    total = max(await rankings_count(), 1)
    rank = int(stat.leaderboard_rank or 1)
    return {"recruiter": items[0], "rank_percentile": round((1 - ((rank - 1) / total)) * 100, 2)}


_RECRUITER_ONLY = {"role": {"$nin": ["admin", "maintainer"]}}


async def fetch_monthly_growth() -> dict[str, Any]:
    stats = (
        await EmployeeStat.find(EmployeeStat.is_active == True)  # noqa: E712
        .sort("-total_score")
        .limit(10)
        .to_list()
    )
    ids = [stat.employee_id for stat in stats]
    monthly = await _monthly_totals_for_employees(ids)
    employees = (
        await DashboardEmployee.get_motor_collection()
        .find({"_id": {"$in": ids}, **_RECRUITER_ONLY})
        .to_list(length=None)
    )
    employee_by_id = {employee["_id"]: employee for employee in employees}
    labels_rows = (
        await LeaderboardHistory.get_motor_collection()
        .find({"employee_id": {"$in": ids}})
        .sort("month")
        .to_list(length=None)
    )
    raw_labels = [
        _month_label(month) for month in sorted({row["month"] for row in labels_rows})[-6:]
    ]
    labels = ([""] * (6 - len(raw_labels)) + raw_labels) if len(raw_labels) < 6 else raw_labels
    series = []
    for stat in stats:
        employee = employee_by_id.get(stat.employee_id)
        if employee is None:
            continue
        series.append(
            {
                "employee_id": str(employee["_id"]),
                "name": employee["name"],
                "monthlyData": monthly.get(str(employee["_id"]), [0, 0, 0, 0, 0, 0]),
            }
        )
    return {"labels": labels, "series": series}


async def fetch_company_progress(limit: int = 8) -> list[dict[str, Any]]:
    jobs = (
        await JobOpening.get_motor_collection()
        .find({"is_active": True})
        .sort("total_seats", -1)
        .limit(limit)
        .to_list(length=None)
    )
    cursor = await CandidateMapping.get_motor_collection().aggregate(  # type: ignore
        [
            {
                "$group": {
                    "_id": "$position_id",
                    "recruiters": {"$addToSet": "$employee_id"},
                    "candidate_count": {"$sum": 1},
                }
            },
        ]
    )
    mappings = await cursor.to_list(length=None)
    mapping_by_job = {item["_id"]: item for item in mappings}
    return [
        {
            "company": job.get("client_name", ""),
            "role": job.get("role", ""),
            "totalSeats": int(job.get("total_seats", 0)),
            "filled": int(job.get("filled_seats", 0)),
            "recruiterCount": len(mapping_by_job.get(job["_id"], {}).get("recruiters", [])),
        }
        for job in jobs
    ]


async def fetch_activity(page: int, limit: int) -> dict[str, Any]:
    cursor = await RecruiterActivity.get_motor_collection().aggregate(  # type: ignore
        [
            {"$sort": {"created_at": -1}},
            {
                "$facet": {
                    "items": [
                        {"$skip": (page - 1) * limit},
                        {"$limit": limit},
                        {
                            "$lookup": {
                                "from": "employees",
                                "localField": "employee_id",
                                "foreignField": "_id",
                                "as": "employee",
                            }
                        },
                        {"$unwind": "$employee"},
                    ],
                    "total": [{"$count": "count"}],
                }
            },
        ]
    )
    result = await cursor.to_list(length=None)
    payload = result[0] if result else {"items": [], "total": []}
    return {
        "items": payload.get("items", []),
        "total": int(payload.get("total", [{}])[0].get("count", 0)) if payload.get("total") else 0,
        "page": page,
        "limit": limit,
    }


async def fetch_badges(employee_id: str) -> dict[str, Any]:
    oid = to_object_id(employee_id, "employee_id")
    if oid is None:
        return {"employee_id": employee_id, "badges": []}
    definitions = await Badge.find_all().to_list()
    stat = await EmployeeStat.find_one(EmployeeStat.employee_id == oid)
    unlocked = {badge.value for badge in stat.badges} if stat else set()
    return {
        "employee_id": employee_id,
        "badges": [
            {
                "key": badge.name,
                "label": badge.label,
                "description": badge.description,
                "icon": badge.icon,
                "rarity": badge.rarity,
                "xp_reward": badge.xp_reward,
                "unlocked": badge.name.value in unlocked,
            }
            for badge in definitions
        ],
    }

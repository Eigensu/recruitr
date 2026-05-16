"""Business logic and cache orchestration for leaderboard."""

from __future__ import annotations

from app.common.dtos.pagination import PaginationMeta
from app.modules.leaderboard.enums import ActivityTypeEnum
from app.modules.leaderboard.repository import (
    create_monthly_snapshots,
    fetch_activity,
    fetch_badges,
    fetch_company_progress,
    fetch_monthly_growth,
    fetch_overview,
    fetch_rankings,
    fetch_recruiter,
    recompute_ranks,
    record_activity_atomic,
)
from app.modules.leaderboard.schemas import (
    ActivityItem,
    ActivityPage,
    BadgeDefinitionResponse,
    CompanyProgressItem,
    CompanyProgressResponse,
    LeaderboardFilters,
    LeaderboardKpi,
    LeaderboardOverviewResponse,
    LeaderboardPage,
    LeaderboardRecruiterItem,
    MonthlyGrowthResponse,
    MonthlyGrowthSeries,
    RecruiterBadgesResponse,
)
from app.modules.leaderboard.utils.cache_manager import (
    get_cached,
    invalidate_leaderboard_cache,
    response_key,
    set_cached,
)

TONE_MAP = {
    ActivityTypeEnum.MAPPING_COMPLETED.value: "neutral",
    ActivityTypeEnum.OFFER_RECEIVED.value: "yellow",
    ActivityTypeEnum.CANDIDATE_JOINED.value: "green",
    ActivityTypeEnum.CANDIDATE_REJECTED.value: "red",
    ActivityTypeEnum.BADGE_UNLOCKED.value: "yellow",
    ActivityTypeEnum.RANK_INCREASED.value: "green",
}


def _page_meta(total: int, page: int, limit: int) -> PaginationMeta:
    pages = 0 if total == 0 else (total + limit - 1) // limit
    return PaginationMeta(
        page=page, limit=limit, total=total, pages=pages, has_next=page < pages, has_prev=page > 1
    )


def _cache_ttl_key(prefix: str, payload: dict | None = None) -> str:
    return response_key(prefix, payload)


def _conversion_rate(summary: dict[str, object]) -> float:
    offers = int(summary.get("offers", 0) or 0)
    if offers <= 0:
        return 0
    joins = int(summary.get("joins", 0) or 0)
    return round((joins / offers) * 100, 2)


async def get_rankings(filters: LeaderboardFilters) -> LeaderboardPage:
    key = _cache_ttl_key("rankings", filters.model_dump(mode="json"))
    cached = await get_cached(key)
    if cached is not None:
        return LeaderboardPage.model_validate(cached)
    payload = await fetch_rankings(
        page=filters.page,
        limit=filters.limit,
        search=filters.search,
        sort_by=filters.sort_by,
        month=filters.month,
    )
    response = LeaderboardPage(
        items=[LeaderboardRecruiterItem.model_validate(item) for item in payload["items"]],
        meta=_page_meta(payload["total"], payload["page"], payload["limit"]),
    )
    await set_cached(key, response.model_dump(mode="json"))
    return response


async def get_overview() -> LeaderboardOverviewResponse:
    key = _cache_ttl_key("overview")
    cached = await get_cached(key)
    if cached is not None:
        return LeaderboardOverviewResponse.model_validate(cached)
    payload = await fetch_overview()
    summary = payload["summary"]
    top = payload["top_recruiter"]
    kpis = [
        LeaderboardKpi(
            id="total_recruiters",
            label="Active Recruiters",
            value=int(summary.get("recruiters", 0)),
            helper="Competing this month",
            tone="yellow",
        ),
        LeaderboardKpi(
            id="total_mappings",
            label="Total Mappings",
            value=int(summary.get("mappings", 0)),
            helper="Across all recruiters",
            tone="neutral",
        ),
        LeaderboardKpi(
            id="offers_sent",
            label="Offers Sent",
            value=int(summary.get("offers", 0)),
            helper="Profiles sent to clients",
            tone="navy",
        ),
        LeaderboardKpi(
            id="successful_joins",
            label="Successful Joins",
            value=int(summary.get("joins", 0)),
            helper="Onboarded this cycle",
            tone="green",
        ),
        LeaderboardKpi(
            id="conversion_rate",
            label="Conversion Rate",
            value=_conversion_rate(summary),
            suffix="%",
            helper="Offers to joins",
            tone="yellow",
        ),
        LeaderboardKpi(
            id="monthly_growth",
            label="Avg Monthly Growth",
            value=round(float(summary.get("growth") or 0), 2),
            suffix="%",
            helper="Team-wide MoM",
            tone="green",
        ),
        LeaderboardKpi(
            id="active_companies",
            label="Active Companies",
            value=int(summary.get("companies", 0)),
            helper="Open hiring mandates",
            tone="neutral",
        ),
        LeaderboardKpi(
            id="top_score",
            label="Top XP Score",
            value=int(summary.get("top_score", 0)),
            helper=top["name"] if top else "No leader yet",
            tone="yellow",
        ),
    ]
    response = LeaderboardOverviewResponse(
        kpis=kpis, top_recruiter=LeaderboardRecruiterItem.model_validate(top) if top else None
    )
    await set_cached(key, response.model_dump(mode="json"))
    return response


async def get_recruiter(employee_id: str):
    payload = await fetch_recruiter(employee_id)
    if payload is None:
        return None
    return {
        "recruiter": LeaderboardRecruiterItem.model_validate(payload["recruiter"]),
        "rank_percentile": float(payload["rank_percentile"]),
    }


async def get_monthly_growth() -> MonthlyGrowthResponse:
    key = _cache_ttl_key("monthly-growth")
    cached = await get_cached(key)
    if cached is not None:
        return MonthlyGrowthResponse.model_validate(cached)
    payload = await fetch_monthly_growth()
    response = MonthlyGrowthResponse(
        labels=payload["labels"],
        series=[MonthlyGrowthSeries.model_validate(item) for item in payload["series"]],
    )
    await set_cached(key, response.model_dump(mode="json"))
    return response


async def get_company_progress() -> CompanyProgressResponse:
    key = _cache_ttl_key("company-progress")
    cached = await get_cached(key)
    if cached is not None:
        return CompanyProgressResponse.model_validate(cached)
    rows = await fetch_company_progress()
    response = CompanyProgressResponse(
        items=[CompanyProgressItem.model_validate(row) for row in rows]
    )
    await set_cached(key, response.model_dump(mode="json"))
    return response


async def get_activities(page: int, limit: int) -> ActivityPage:
    payload = await fetch_activity(page, limit)
    items = []
    for row in payload["items"]:
        employee = row["employee"]
        items.append(
            ActivityItem(
                id=str(row["_id"]),
                recruiter=employee["name"],
                initials="".join(part[:1] for part in employee["name"].split()[:2]).upper() or "NA",
                action=row["title"],
                target=row["description"],
                timestamp=row["created_at"],
                tone=TONE_MAP.get(row["activity_type"], "neutral"),
                avatarColor=employee.get("avatar_color") or "#F3FF54",
                activity_type=row["activity_type"],
            )
        )
    return ActivityPage(
        items=items, meta=_page_meta(payload["total"], payload["page"], payload["limit"])
    )


async def get_badges(employee_id: str) -> RecruiterBadgesResponse:
    payload = await fetch_badges(employee_id)
    badges = [BadgeDefinitionResponse.model_validate(item) for item in payload["badges"]]
    return RecruiterBadgesResponse(employee_id=payload["employee_id"], badges=badges)


async def handle_activity(
    employee_id: str,
    candidate_id: str | None,
    activity_type: ActivityTypeEnum,
    reference_id: str,
    title: str,
    description: str,
) -> bool:
    processed = await record_activity_atomic(
        employee_id=employee_id,
        candidate_id=candidate_id,
        activity_type=activity_type,
        activity_reference_id=reference_id,
        title=title,
        description=description,
    )
    if processed:
        await invalidate_leaderboard_cache()
    return processed


async def refresh_rankings() -> None:
    await recompute_ranks()
    await invalidate_leaderboard_cache()


async def refresh_monthly_snapshot(month: str) -> int:
    count = await create_monthly_snapshots(month)
    await invalidate_leaderboard_cache()
    return count

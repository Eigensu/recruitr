"""The badge catalogue: what each badge is called, shows and is worth.

Badge definitions live in the `badges` collection and nothing in the app writes
them; GET /leaderboard/badges/{employee_id} lists whatever is there. They used to
be loaded by the leaderboard demo seeder, removed once its demo data stopped
matching the models, so the catalogue lives here on its own.

    python -m app.modules.leaderboard.badge_catalog
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from app.common.utils.seed_guard import assert_local_database
from app.core.config import settings
from app.modules.leaderboard.enums import BadgeRarityEnum, BadgeTypeEnum

BADGES = [
    (
        BadgeTypeEnum.TOP_MAPPER,
        "Top Mapper",
        "Mapped 100+ candidates this month",
        "🗺️",
        BadgeRarityEnum.EPIC,
        300,
        "total_mappings",
        100,
    ),
    (
        BadgeTypeEnum.HIRING_CHAMPION,
        "Hiring Champion",
        "Closed 25 successful joins",
        "🏆",
        BadgeRarityEnum.LEGENDARY,
        500,
        "joined_candidates",
        25,
    ),
    (
        BadgeTypeEnum.OFFER_KING,
        "Offer King",
        "Generated 50 offers in one cycle",
        "👑",
        BadgeRarityEnum.LEGENDARY,
        450,
        "offers_received",
        50,
    ),
    (
        BadgeTypeEnum.CONSISTENCY_STAR,
        "Consistency Star",
        "Maintained a 30-day streak",
        "⭐",
        BadgeRarityEnum.RARE,
        250,
        "streak_days",
        30,
    ),
    (
        BadgeTypeEnum.RISING_RECRUITER,
        "Rising Recruiter",
        "Reached 20% month-over-month growth",
        "🚀",
        BadgeRarityEnum.COMMON,
        150,
        "monthly_growth",
        20,
    ),
    (
        BadgeTypeEnum.FAST_CLOSER,
        "Fast Closer",
        "Closed 10 joins during a strong streak",
        "⚡",
        BadgeRarityEnum.RARE,
        275,
        "fast_close",
        10,
    ),
    (
        BadgeTypeEnum.ELITE_RECRUITER,
        "Elite Recruiter",
        "Top-tier recruiter across all metrics",
        "💎",
        BadgeRarityEnum.LEGENDARY,
        650,
        "score",
        900,
    ),
    (
        BadgeTypeEnum.RECRUITMENT_NINJA,
        "Recruitment Ninja",
        "High joins with minimal rejections",
        "🥷",
        BadgeRarityEnum.EPIC,
        325,
        "join_quality",
        10,
    ),
]


async def upsert_badges(db: AsyncDatabase) -> int:
    """Write every definition in BADGES, keyed by name, and return how many."""
    for (
        name,
        label,
        description,
        icon,
        rarity,
        xp_reward,
        condition_type,
        condition_value,
    ) in BADGES:
        await db["badges"].update_one(
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
                },
                # Only on insert: a re-run updates the definition, not when it was made.
                "$setOnInsert": {"created_at": datetime.now(UTC)},
            },
            upsert=True,
        )
    return len(BADGES)


async def _main() -> None:
    assert_local_database(settings.MONGODB_URI, action="load the badge catalogue into")
    async with AsyncMongoClient(settings.MONGODB_URI) as client:
        count = await upsert_badges(client[settings.MONGODB_DB_NAME])
    print(f"Badges: {count}")


if __name__ == "__main__":
    asyncio.run(_main())

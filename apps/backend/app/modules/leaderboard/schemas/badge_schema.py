from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.modules.leaderboard.enums import BadgeRarityEnum, BadgeTypeEnum


class BadgeDefinitionResponse(BaseModel):
    key: BadgeTypeEnum
    label: str
    description: str
    icon: str
    rarity: BadgeRarityEnum
    xp_reward: int
    unlocked: bool = False


class RecruiterBadgesResponse(BaseModel):
    employee_id: str
    badges: list[BadgeDefinitionResponse]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

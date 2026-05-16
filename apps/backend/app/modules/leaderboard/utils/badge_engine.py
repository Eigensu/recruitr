from app.modules.leaderboard.enums import BadgeTypeEnum


def evaluate_badges(stats: dict) -> list[BadgeTypeEnum]:
    mappings = stats.get("mappings", {})
    total = int(mappings.get("total_mappings", 0))
    offers = int(mappings.get("offers_received", 0))
    joined = int(mappings.get("joined_candidates", 0))
    rejected = int(mappings.get("rejected_candidates", 0))
    growth = float(stats.get("monthly_growth", 0))
    streak = int(stats.get("streak_days", 0))
    score = int(stats.get("total_score", 0))
    success = 0 if offers <= 0 else (joined / offers) * 100

    earned: list[BadgeTypeEnum] = []
    if total >= 100:
        earned.append(BadgeTypeEnum.TOP_MAPPER)
    if joined >= 25:
        earned.append(BadgeTypeEnum.HIRING_CHAMPION)
    if offers >= 50:
        earned.append(BadgeTypeEnum.OFFER_KING)
    if streak >= 30 or success >= 80:
        earned.append(BadgeTypeEnum.CONSISTENCY_STAR)
    if growth >= 20:
        earned.append(BadgeTypeEnum.RISING_RECRUITER)
    if joined >= 10 and streak >= 7:
        earned.append(BadgeTypeEnum.FAST_CLOSER)
    if score >= 900 or (success >= 85 and total >= 75):
        earned.append(BadgeTypeEnum.ELITE_RECRUITER)
    if joined >= 10 and rejected <= max(3, joined // 3):
        earned.append(BadgeTypeEnum.RECRUITMENT_NINJA)
    return earned


def primary_badge(badges: list[BadgeTypeEnum]) -> BadgeTypeEnum:
    priority = [
        BadgeTypeEnum.ELITE_RECRUITER,
        BadgeTypeEnum.HIRING_CHAMPION,
        BadgeTypeEnum.OFFER_KING,
        BadgeTypeEnum.TOP_MAPPER,
        BadgeTypeEnum.FAST_CLOSER,
        BadgeTypeEnum.CONSISTENCY_STAR,
        BadgeTypeEnum.RECRUITMENT_NINJA,
        BadgeTypeEnum.RISING_RECRUITER,
    ]
    for badge in priority:
        if badge in badges:
            return badge
    return BadgeTypeEnum.RISING_RECRUITER

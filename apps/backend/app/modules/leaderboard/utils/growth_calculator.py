def percent_growth(current: int, previous: int) -> float:
    if previous <= 0:
        return 100.0 if current > 0 else 0.0
    return round(((current - previous) / previous) * 100, 2)


def success_rate(joined: int, offers: int) -> float:
    if offers <= 0:
        return 0.0
    return round((joined / offers) * 100, 2)
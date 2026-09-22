from datetime import UTC, datetime


def normalize_datetime(dt: datetime) -> datetime:
    """Normalize datetime to naive UTC for safe comparison and database storage."""
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt

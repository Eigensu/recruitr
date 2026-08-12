from datetime import UTC, date, datetime

from app.modules.dashboard.referee_service import _get_next_working_day, calculate_incentive_amount


def test_matrix():
    assert calculate_incentive_amount("Entry", 1) == 1000.0
    assert calculate_incentive_amount("Entry", 2) == 1000.0
    assert calculate_incentive_amount("Entry", 3) == 1200.0
    assert calculate_incentive_amount("Entry", 4) == 1200.0
    assert calculate_incentive_amount("Entry", 5) == 1500.0
    assert calculate_incentive_amount("Mid", 1) == 800.0
    assert calculate_incentive_amount("Mid", 2) == 800.0
    assert calculate_incentive_amount("Mid", 3) == 1000.0
    assert calculate_incentive_amount("Mid", 4) == 1000.0
    assert calculate_incentive_amount("Mid", 5) == 1200.0

    # Mixed 3-placement
    refs = [("Entry",), ("Entry",), ("Mid",)]
    total = sum(calculate_incentive_amount(r[0], len(refs)) for r in refs)
    assert total == 3400.0


def test_dates():
    d = datetime(2026, 8, 7, tzinfo=UTC)  # Friday
    assert _get_next_working_day(d).date() == date(2026, 8, 7)

    d2 = datetime(2026, 8, 8, tzinfo=UTC)  # Saturday
    assert _get_next_working_day(d2).date() == date(2026, 8, 10)  # Monday

    d3 = datetime(2026, 8, 9, tzinfo=UTC)  # Sunday
    assert _get_next_working_day(d3).date() == date(2026, 8, 10)  # Monday


test_matrix()
test_dates()
print("TESTS PASSED")

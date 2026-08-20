import pytest

from app.modules.recruitment.enums.department import Department
from app.modules.recruitment.schemas.position import PositionCreate


def test_create_boh_valid():
    pos = PositionCreate(
        client_id="123", role="Sous Chef", department=Department.boh, total_seats=1
    )
    assert pos.role == "Sous Chef"


def test_create_service_valid():
    pos = PositionCreate(
        client_id="123", role="Bartender", department=Department.service, total_seats=1
    )
    assert pos.role == "Bartender"


def test_create_corporate_valid():
    pos = PositionCreate(client_id="123", role="HR", department=Department.corporate, total_seats=1)
    assert pos.role == "HR"


def test_boh_bartender_invalid():
    with pytest.raises(ValueError, match="Role 'Bartender' is not valid for category 'BOH'"):
        PositionCreate(client_id="123", role="Bartender", department=Department.boh, total_seats=1)


def test_service_sous_chef_invalid():
    with pytest.raises(ValueError, match="Role 'Sous Chef' is not valid for category 'Service'"):
        PositionCreate(
            client_id="123", role="Sous Chef", department=Department.service, total_seats=1
        )


def test_invalid_department():
    with pytest.raises(ValueError):
        PositionCreate(client_id="123", role="Sous Chef", department="Kitchen", total_seats=1)


def test_mumbai_without_area():
    pos = PositionCreate(
        client_id="123", role="Sous Chef", department=Department.boh, city="Mumbai", total_seats=1
    )
    assert pos.city == "Mumbai"
    assert pos.mumbai_area is None


def test_mumbai_with_area():
    pos = PositionCreate(
        client_id="123",
        role="Sous Chef",
        department=Department.boh,
        city="Mumbai",
        mumbai_area="Andheri",
        total_seats=1,
    )
    assert pos.city == "Mumbai"
    assert pos.mumbai_area == "Andheri"


def test_non_mumbai_with_mumbai_area():
    pos = PositionCreate(
        client_id="123",
        role="Sous Chef",
        department=Department.boh,
        city="Pune",
        mumbai_area="Andheri",
        total_seats=1,
    )
    assert pos.city == "Pune"
    assert pos.mumbai_area is None

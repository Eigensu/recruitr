from datetime import UTC, datetime, timedelta

import pytest
from beanie import PydanticObjectId

from app.modules.brands.models import Brand
from app.modules.recruitment.enums.pipeline_stage import PipelineStage
from app.modules.recruitment.models import Candidate, ClientUser, Mapping, Position
from app.modules.recruitment.tasks import _process_reminders_async


@pytest.fixture
def mock_email_service(monkeypatch):
    sent_emails = []

    def mock_client_action(*args, **kwargs):
        sent_emails.append(("client_action", kwargs.get("email")))

    def mock_interview_followup(*args, **kwargs):
        sent_emails.append(("interview_followup", kwargs.get("email")))

    def mock_offer_upload(*args, **kwargs):
        sent_emails.append(("offer_upload", kwargs.get("email")))

    monkeypatch.setattr(
        "app.modules.dashboard.email_service.EmailService.send_client_action_reminder",
        mock_client_action,
    )
    monkeypatch.setattr(
        "app.modules.dashboard.email_service.EmailService.send_interview_followup",
        mock_interview_followup,
    )
    monkeypatch.setattr(
        "app.modules.dashboard.email_service.EmailService.send_offer_upload_reminder",
        mock_offer_upload,
    )
    return sent_emails


@pytest.mark.asyncio
async def test_process_reminders(
    mock_email_service: list[tuple[str, str]],
    init_test_db: None,
) -> None:
    now = datetime.now(UTC)
    three_days_ago = now - timedelta(days=3)

    # 1. Setup Data
    brand = Brand(name="Test Brand", owner_id=str(PydanticObjectId()), domain="test.com")
    await brand.insert()

    client_id = PydanticObjectId()
    client_user = ClientUser(
        brand_id=brand.id,
        client_id=client_id,
        email="client@test.com",
        name="Client A",
        is_active=True,
    )
    await client_user.insert()

    position = Position(
        brand_id=brand.id,
        code="POS-1",
        client_id=client_id,
        client_name="Test Client",
        role="Chef",
    )
    await position.insert()

    candidate_a = Candidate(
        brand_id=brand.id,
        full_name="A",
        email="a@test.com",
        phone="1",
        experience_years=2,
        communication="Good",
        education="Bachelors",
        department="Service",
        city="Mumbai",
        gender="male",
        expected_salary=1000,
        source="internal",
    )
    await candidate_a.insert()

    candidate_b = Candidate(
        brand_id=brand.id,
        full_name="B",
        email="b@test.com",
        phone="2",
        experience_years=2,
        communication="Good",
        education="Bachelors",
        department="Service",
        city="Mumbai",
        gender="male",
        expected_salary=1000,
        source="internal",
    )
    await candidate_b.insert()

    candidate_c = Candidate(
        brand_id=brand.id,
        full_name="C",
        email="c@test.com",
        phone="3",
        experience_years=2,
        communication="Good",
        education="Bachelors",
        department="Service",
        city="Mumbai",
        gender="male",
        expected_salary=1000,
        source="internal",
    )
    await candidate_c.insert()

    # Create Mappings that qualify for reminders
    # A. Client Action (> 2 days in sent_to_client)
    mapping_a = Mapping(
        brand_id=brand.id,
        candidate_id=candidate_a.id,
        position_id=position.id,
        client_id=client_id,
        employee_id=PydanticObjectId(),
        stage=PipelineStage.sent_to_client,
        updated_at=three_days_ago,
    )
    await mapping_a.insert()

    # B. Interview Follow-up (> 2 days since interview_date)
    mapping_b = Mapping(
        brand_id=brand.id,
        candidate_id=candidate_b.id,
        position_id=position.id,
        client_id=client_id,
        employee_id=PydanticObjectId(),
        stage=PipelineStage.interview,
        interview_date=three_days_ago,
        updated_at=three_days_ago,
    )
    await mapping_b.insert()

    # C. Offer Upload (> 2 days since selected, no offer letter)
    mapping_c = Mapping(
        brand_id=brand.id,
        candidate_id=candidate_c.id,
        position_id=position.id,
        client_id=client_id,
        employee_id=PydanticObjectId(),
        stage=PipelineStage.selected,
        updated_at=three_days_ago,
    )
    await mapping_c.insert()

    # Run processor
    await _process_reminders_async()

    # Assert Emails were "sent"
    assert ("client_action", "client@test.com") in mock_email_service
    assert ("interview_followup", "client@test.com") in mock_email_service
    assert ("offer_upload", "client@test.com") in mock_email_service
    assert len(mock_email_service) == 3

    mock_email_service.clear()

    # Run processor again (idempotency check)
    await _process_reminders_async()
    assert len(mock_email_service) == 0  # No new emails sent

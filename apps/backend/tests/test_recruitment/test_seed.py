"""The local seeder writes documents the app can read back.

It inserts raw dicts, so nothing checked them against the models: once
Position.department became a BOH/Service/Corporate enum the seeder kept writing
"F&B - Service", and every seeded position failed to load. Reading each
collection back through its model catches the next field that drifts the same way.
"""

from app.core.config import settings
from app.modules.brands.models import Brand
from app.modules.recruitment import seed as recruitment_seed
from app.modules.recruitment.models import (
    ActivityLog,
    Candidate,
    Client,
    Counter,
    Employee,
    Mapping,
    Position,
    RecruiterTag,
    Team,
)

_SEEDED = (
    Brand,
    Team,
    RecruiterTag,
    Employee,
    Client,
    Position,
    Candidate,
    Mapping,
    ActivityLog,
    Counter,
)


async def test_every_seeded_document_loads_through_its_model(monkeypatch):
    # The per-test database, which the conftest fixture drops afterwards.
    monkeypatch.setattr(settings, "MONGODB_DB_NAME", f"{settings.MONGODB_DB_NAME}_test")

    await recruitment_seed.seed()

    for model in _SEEDED:
        assert await model.find_all().to_list(), f"nothing seeded for {model.__name__}"

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_celery_tasks():
    with patch(
        "app.modules.recruitment.tasks.process_new_position_notifications.delay"
    ) as mock_delay:
        yield mock_delay

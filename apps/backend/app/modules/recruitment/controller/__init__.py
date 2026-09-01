"""Recruitment API controllers (routers)."""

from app.modules.recruitment.controller.activity import router as activity_router
from app.modules.recruitment.controller.candidates import router as candidates_router
from app.modules.recruitment.controller.client_messaging import router as client_messaging_router
from app.modules.recruitment.controller.clients import router as clients_router
from app.modules.recruitment.controller.pipeline import router as pipeline_router
from app.modules.recruitment.controller.positions import router as positions_router
from app.modules.recruitment.controller.public_controller import router as public_router
from app.modules.recruitment.controller.referees import router as referees_router
from app.modules.recruitment.controller.tags import router as tags_router
from app.modules.recruitment.controller.tasks import router as tasks_router
from app.modules.recruitment.controller.teams import router as teams_router

__all__ = [
    "activity_router",
    "candidates_router",
    "client_messaging_router",
    "clients_router",
    "pipeline_router",
    "positions_router",
    "public_router",
    "referees_router",
    "tags_router",
    "teams_router",
    "tasks_router",
]

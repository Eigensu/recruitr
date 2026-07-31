"""Recruitment API controllers (routers)."""

from app.modules.recruitment.controller.activity import router as activity_router
from app.modules.recruitment.controller.candidates import router as candidates_router
from app.modules.recruitment.controller.clients import router as clients_router
from app.modules.recruitment.controller.pipeline import router as pipeline_router
from app.modules.recruitment.controller.positions import router as positions_router
from app.modules.recruitment.controller.tags import router as tags_router
from app.modules.recruitment.controller.teams import router as teams_router

__all__ = [
    "activity_router",
    "candidates_router",
    "clients_router",
    "positions_router",
    "pipeline_router",
    "tags_router",
    "teams_router",
]

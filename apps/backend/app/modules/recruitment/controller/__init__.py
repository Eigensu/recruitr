"""Recruitment API controllers (routers)."""

from app.modules.recruitment.controller.candidates import router as candidates_router
from app.modules.recruitment.controller.pipeline import router as pipeline_router
from app.modules.recruitment.controller.positions import router as positions_router

__all__ = ["candidates_router", "positions_router", "pipeline_router"]

"""Recruitment business logic services.

During Phase C/D refactoring, services will be split into focused modules:
- candidate_service.py
- position_service.py
- mapping_service.py

For now, re-export from the root service.py module.
"""

from app.modules.recruitment.service_impl import (
    advance_stage,
    ensure_employee_for_user,
    map_candidate,
    unmap_candidate,
)

__all__ = [
    "ensure_employee_for_user",
    "map_candidate",
    "unmap_candidate",
    "advance_stage",
]

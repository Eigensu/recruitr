"""Recruitment business logic — the package's public surface.

This is the facade: import business logic from `...recruitment.service`, not
from the modules underneath it, so the split below can move without touching
callers. `service_impl.py` is still the catch-all and is meant to be broken up
into focused modules (candidate, position, mapping) as the refactor continues;
`resume_service.py` is the first piece already carved out.

There used to be a sibling `services/` package holding those implementations,
one letter away from this one. They are now a single package.
"""

from app.modules.recruitment.service.service_impl import (
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

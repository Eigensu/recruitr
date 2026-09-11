"""Recruitment business logic — the package's public surface.

Import from here, not from `_impl`: the underscore marks that module private to
this package, so the split below can happen without touching callers.
`_impl.py` is still the catch-all and is meant to be broken up into focused
modules (candidate, position, mapping) as the refactor continues;
`resume_service.py` is the first piece already carved out.

There used to be a sibling `services/` package holding those implementations,
one letter away from this one. They are now a single package.
"""

from app.modules.recruitment.service._impl import (
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

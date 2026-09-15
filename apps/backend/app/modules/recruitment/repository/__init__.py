"""Recruitment data access layer — the package's public surface.

Import from here, not from `_impl`: the underscore marks that module private to
this package, and routing through the facade is what lets `_impl.py` be split
into per-domain modules later without touching a single caller.

Every function here takes a `TenantScope` and prepends `brand_id` to its query.
"""

from app.modules.recruitment.repository._impl import (
    candidate_display_name,
    create_employee,
    create_mapping,
    delete_mapping,
    find_employee_by_email,
    generate_client_code,
    generate_position_code,
    get_candidate,
    get_client,
    get_mapping,
    get_position,
    link_employee_user,
    list_clients,
    log_activity,
    move_stage,
    next_seq,
    recompute_position_seats,
    record_candidate_event,
    set_seq,
    update_candidate_current_stage,
)

__all__ = [
    "candidate_display_name",
    "create_employee",
    "create_mapping",
    "delete_mapping",
    "find_employee_by_email",
    "generate_client_code",
    "generate_position_code",
    "get_candidate",
    "get_client",
    "get_mapping",
    "get_position",
    "link_employee_user",
    "list_clients",
    "log_activity",
    "move_stage",
    "next_seq",
    "record_candidate_event",
    "recompute_position_seats",
    "set_seq",
    "update_candidate_current_stage",
]

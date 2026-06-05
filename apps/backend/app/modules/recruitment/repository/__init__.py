"""Recruitment data access layer (repositories and queries).

During Phase C/D refactoring, repository will be split into:
- queries.py (read operations)
- writes.py (write operations)

For now, re-export from the root repository_impl.py module.
"""

from app.modules.recruitment.repository_impl import (
    fetch_mappings,
    generate_client_code,
    generate_position_code,
    next_seq,
    set_seq,
)

__all__ = [
    "next_seq",
    "set_seq",
    "generate_client_code",
    "generate_position_code",
    "fetch_mappings",
]

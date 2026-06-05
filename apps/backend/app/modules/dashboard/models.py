"""Dashboard module models — thin re-export layer over the recruitment domain.

All Beanie documents now live in app.modules.recruitment.models.
These aliases preserve any existing imports throughout the codebase.
"""

from app.modules.recruitment.models import (  # noqa: F401
    ActivityLog,
    CandidateDocument,
)
from app.modules.recruitment.models import (
    Candidate as DashboardCandidate,
)
from app.modules.recruitment.models import (
    Employee as DashboardEmployee,
)
from app.modules.recruitment.models import (
    Mapping as CandidateMapping,
)
from app.modules.recruitment.models import (
    Position as JobOpening,
)

__all__ = [
    "ActivityLog",
    "CandidateDocument",
    "CandidateMapping",
    "DashboardCandidate",
    "DashboardEmployee",
    "JobOpening",
]

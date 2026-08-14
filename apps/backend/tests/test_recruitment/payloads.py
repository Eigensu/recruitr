"""Shared request bodies for the recruitment HTTP tests.

POST /api/v1/candidates validates against `CandidateCreateStrict`, which requires
every recruiter-presented field — a partial body is rejected with 422 before it
reaches the handler. Tests that only care about one field still have to send a
complete one, so the complete one lives here: a schema change breaks this single
constant instead of every module that happens to create a candidate.
"""

from typing import Any

# Values are asserted on by name in test_candidates_api (search-by-name,
# search-by-skill, experience filters), so change them with care.
STRICT_CANDIDATE_PAYLOAD: dict[str, Any] = {
    "full_name": "Priya Nair",
    "email": "priya@test.com",
    "phone": "+91 98765 00000",
    "previous_company": "Taj Hotels",
    "experience_years": 3,
    "skills": ["Guest Relations", "POS", "Billing"],
    "source": "internal",  # "external" additionally requires source_channel + cv_link
    "communication": "fluent",
    "education": "graduate",
    "brand_experience": "luxury",
    "department": "front office",
    "specialization": "guest relations",  # required whenever department is set
    "current_role": "Guest Relations Executive",
    "city": "Mumbai",
    "area": "Andheri",
    "gender": "female",
    "age": 28,
    "expected_salary": 60000,
    "salary": 45000,
    "notice_period": "30 days",
}


def candidate_payload(**overrides: Any) -> dict[str, Any]:
    """A complete, valid POST /api/v1/candidates body with `overrides` applied."""
    return {**STRICT_CANDIDATE_PAYLOAD, **overrides}

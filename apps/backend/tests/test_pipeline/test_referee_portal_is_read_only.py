"""The referee portal exposes no way to change anything.

A referee's view is a tracker: where their referrals got to and what they are
owed. Deciding on a candidate belongs to the recruiter on the recruitment
pipeline and to the client on theirs — a third place a stage can move from is a
third place the pipeline can disagree with itself, and the referee is the one
party with a financial stake in the outcome.

#54 gave the portal Select/Reject and an offer-letter upload. These pin their
removal, so the write surface cannot creep back without someone deciding to.

Every assertion here is guarded against finding nothing: a test that silently
stops discovering routes reports a locked-down portal no matter what the portal
actually exposes.
"""

from app.core.main import app

PREFIX = "/api/v1/referee-dashboard"


def _referee_operations() -> dict[str, set[str]]:
    """Portal path -> the HTTP methods it accepts, read from the OpenAPI schema.

    Not app.routes. FastAPI 0.141 keeps an included router in an _IncludedRouter
    wrapper that carries no .path, so scanning app.routes there matches nothing
    and these assertions pass while checking an empty set — the failure mode
    this guard exists to prevent. The schema is public API and lists the same
    routes on either version.
    """
    return {
        path: {method.upper() for method in methods}
        for path, methods in app.openapi()["paths"].items()
        if path.startswith(PREFIX)
    }


def test_the_portal_exposes_no_write_endpoint():
    operations = _referee_operations()

    assert operations, "No referee routes found — route discovery is broken, not the portal"
    for path, methods in operations.items():
        assert methods <= {"GET"}, f"{path} accepts {sorted(methods)}"


def test_the_referee_stage_move_is_gone():
    paths = set(_referee_operations())

    assert f"{PREFIX}/referrals/{{mapping_id}}/move" not in paths
    assert f"{PREFIX}/referrals/{{mapping_id}}/offer-letter" not in paths


def test_the_three_reads_survive():
    assert set(_referee_operations()) == {
        f"{PREFIX}/summary",
        f"{PREFIX}/referrals",
        f"{PREFIX}/payments",
    }

"""The referee portal exposes no way to change anything.

A referee's view is a tracker: where their referrals got to and what they are
owed. Deciding on a candidate belongs to the recruiter on the recruitment
pipeline and to the client on theirs — a third place a stage can move from is a
third place the pipeline can disagree with itself, and the referee is the one
party with a financial stake in the outcome.

#54 gave the portal Select/Reject and an offer-letter upload. These pin their
removal, so the write surface cannot creep back without someone deciding to.
"""

from app.main import app

PREFIX = "/api/v1/referee-dashboard"


def _referee_routes():
    return [r for r in app.routes if getattr(r, "path", "").startswith(PREFIX)]


def test_the_portal_exposes_no_write_endpoint():
    for route in _referee_routes():
        assert set(route.methods) <= {"GET", "HEAD", "OPTIONS"}, (
            f"{route.path} accepts {sorted(route.methods)}"
        )


def test_the_referee_stage_move_is_gone():
    paths = {r.path for r in _referee_routes()}

    assert f"{PREFIX}/referrals/{{mapping_id}}/move" not in paths
    assert f"{PREFIX}/referrals/{{mapping_id}}/offer-letter" not in paths


def test_the_three_reads_survive():
    paths = {r.path for r in _referee_routes()}

    assert paths == {
        f"{PREFIX}/summary",
        f"{PREFIX}/referrals",
        f"{PREFIX}/payments",
    }

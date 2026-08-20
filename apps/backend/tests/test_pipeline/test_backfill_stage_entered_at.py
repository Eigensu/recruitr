"""Cover the stage_entered_at backfill before it is pointed at real data.

Uses a synchronous pymongo handle on a scratch database rather than the Beanie
fixture: the script under test is standalone and talks raw pymongo, and this
keeps it honest about what it actually does to documents.
"""

from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from pymongo import MongoClient

from app.config import settings
from scripts.backfill_stage_entered_at import _needs_backfill, apply, plan

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC).replace(tzinfo=None)


@pytest.fixture
def db():
    client = MongoClient(settings.MONGODB_URI)
    name = f"{settings.MONGODB_DB_NAME}_backfill_test"
    client.drop_database(name)
    yield client[name]
    client.drop_database(name)
    client.close()


def _mapping(db, *, stage, history, candidate_id=None):
    cid = candidate_id or ObjectId()
    oid = db.candidate_mappings.insert_one(
        {"stage": stage, "history": history, "candidate_id": cid, "mapped_at": NOW}
    ).inserted_id
    return oid, cid


def _event(db, cid, *, to_stage, at, from_stage=None):
    db.candidate_events.insert_one(
        {"candidate_id": cid, "to_stage": to_stage, "from_stage": from_stage, "at": at}
    )


def test_needs_backfill_detects_missing_event():
    assert _needs_backfill({"stage": "joined", "history": [{"stage": "selected"}]})
    assert _needs_backfill({"stage": "joined", "history": []})
    assert not _needs_backfill({"stage": "joined", "history": [{"stage": "joined"}]})


def test_recovers_entry_time_from_candidate_events(db):
    entered = NOW - timedelta(days=2)
    oid, cid = _mapping(
        db, stage="joined", history=[{"stage": "selected", "at": NOW - timedelta(days=40)}]
    )
    _event(db, cid, to_stage="joined", at=entered, from_stage="selected")

    planned, unexplained = plan(db)
    assert len(planned) == 1 and not unexplained
    assert apply(db.candidate_mappings, planned) == 1

    history = db.candidate_mappings.find_one({"_id": oid})["history"]
    assert [h["stage"] for h in history] == ["selected", "joined"]
    assert history[-1]["at"] == entered
    # Reconstructed, so it must not read as a recruiter's own action.
    assert history[-1]["actor"] == "system"
    assert history[-1]["from_stage"] == "selected"


def test_picks_the_newest_event_when_a_stage_is_re_entered(db):
    older = NOW - timedelta(days=30)
    newer = NOW - timedelta(days=3)
    oid, cid = _mapping(
        db, stage="interview", history=[{"stage": "sourced", "at": NOW - timedelta(days=60)}]
    )
    _event(db, cid, to_stage="interview", at=older)
    _event(db, cid, to_stage="interview", at=newer)

    planned, _ = plan(db)
    apply(db.candidate_mappings, planned)

    assert db.candidate_mappings.find_one({"_id": oid})["history"][-1]["at"] == newer


def test_leaves_mappings_no_event_explains(db):
    _mapping(db, stage="rejected", history=[{"stage": "selected", "at": NOW}])

    planned, unexplained = plan(db)
    assert not planned and len(unexplained) == 1
    assert apply(db.candidate_mappings, planned) == 0


def test_skips_an_event_older_than_the_trail_it_would_join(db):
    # Appending this would put history out of chronological order.
    oid, cid = _mapping(
        db, stage="joined", history=[{"stage": "selected", "at": NOW - timedelta(days=5)}]
    )
    _event(db, cid, to_stage="joined", at=NOW - timedelta(days=90))

    planned, unexplained = plan(db)
    assert not planned and len(unexplained) == 1
    assert len(db.candidate_mappings.find_one({"_id": oid})["history"]) == 1


def test_is_idempotent(db):
    oid, cid = _mapping(
        db, stage="joined", history=[{"stage": "selected", "at": NOW - timedelta(days=40)}]
    )
    _event(db, cid, to_stage="joined", at=NOW - timedelta(days=2))

    planned, _ = plan(db)
    apply(db.candidate_mappings, planned)

    # A second pass sees the event it just wrote and plans nothing.
    planned_again, _ = plan(db)
    assert not planned_again
    assert len(db.candidate_mappings.find_one({"_id": oid})["history"]) == 2


def test_leaves_healthy_mappings_untouched(db):
    oid, _ = _mapping(db, stage="joined", history=[{"stage": "joined", "at": NOW}])

    planned, unexplained = plan(db)
    assert not planned and not unexplained
    assert len(db.candidate_mappings.find_one({"_id": oid})["history"]) == 1

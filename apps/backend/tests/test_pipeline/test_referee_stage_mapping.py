"""Referee-facing stage mapping must stay in step with PipelineStage.

PR #48 collapsed the pipeline from seven forward stages to five, but the referee
map kept three entries keyed on the same PipelineStage.selected — so Python
silently dropped all but the last, and two referee steps became unreachable.

The map is no longer one-to-one, and that is deliberate: two pairs of internal
stages collapse onto a single referee step, and one internal stage has no step at
all. The cases below pin which, so a future edit cannot quietly reintroduce the
duplicate-key collapse under cover of the intended ones.
"""

from app.modules.dashboard.referee_service import (
    _FROZEN_STAGES,
    _REFEREE_STAGE_BY_INTERNAL,
    map_stage_to_referee,
)
from app.modules.recruitment.enums import PipelineStage, RefereeKanbanStage


def test_every_stage_but_the_frozen_one_has_a_referee_step():
    expected = {s.value for s in PipelineStage if s not in _FROZEN_STAGES}

    assert set(_REFEREE_STAGE_BY_INTERNAL) == expected


def test_selected_maps_to_selected():
    assert map_stage_to_referee(PipelineStage.selected.value) == RefereeKanbanStage.selected.value


def test_being_put_in_front_of_a_client_reads_as_cv_reviewed():
    """The referee's meaningful event is the CV reaching a client.

    Whether it is merely mapped or formally sent on is internal detail they
    cannot act on, so both stages collapse onto one step.
    """
    for stage in (PipelineStage.sourced, PipelineStage.sent_to_client):
        assert map_stage_to_referee(stage.value) == RefereeKanbanStage.cv_reviewed.value


def test_a_referral_out_of_play_falls_back_to_cv_reviewed():
    """Leaving it parked at Interview would show progress that no longer exists."""
    for stage in (PipelineStage.rejected, PipelineStage.candidate_dropped):
        assert map_stage_to_referee(stage.value) == RefereeKanbanStage.cv_reviewed.value


def test_the_frozen_stage_has_no_referee_step():
    """on_hold is temporary, so the timeline holds where it was — see
    _stage_for_mapping, which reads the last real stage back out of history."""
    for stage in _FROZEN_STAGES:
        assert stage.value not in _REFEREE_STAGE_BY_INTERNAL


def test_cv_received_is_not_reachable_from_any_stage():
    """It is the state of a candidate with no mapping at all, resolved from the
    absence of mappings rather than from any stage."""
    assert RefereeKanbanStage.cv_received not in set(_REFEREE_STAGE_BY_INTERNAL.values())

"""Referee-facing stage mapping must stay in step with PipelineStage.

PR #48 collapsed the pipeline from seven forward stages to five, but the referee
map kept three entries keyed on the same PipelineStage.selected — so Python
silently dropped all but the last, and two referee steps became unreachable.
"""

from app.modules.dashboard.referee_service import (
    _CLOSED_STAGES,
    _REFEREE_STAGE_BY_INTERNAL,
    map_stage_to_referee,
)
from app.modules.recruitment.enums import PipelineStage, RefereeKanbanStage


def test_every_forward_stage_has_a_distinct_referee_step():
    forward = [s for s in PipelineStage if s not in _CLOSED_STAGES]

    assert set(_REFEREE_STAGE_BY_INTERNAL) == {s.value for s in forward}
    # A duplicate key would collapse two stages onto one step.
    assert len(set(_REFEREE_STAGE_BY_INTERNAL.values())) == len(forward)


def test_every_referee_stage_is_reachable():
    assert set(_REFEREE_STAGE_BY_INTERNAL.values()) == {s.value for s in RefereeKanbanStage}


def test_selected_maps_to_selected():
    assert map_stage_to_referee(PipelineStage.selected.value) == RefereeKanbanStage.selected.value


def test_closed_stages_have_no_referee_step():
    for stage in _CLOSED_STAGES:
        assert stage.value not in _REFEREE_STAGE_BY_INTERNAL

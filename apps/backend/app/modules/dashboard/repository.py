"""MongoDB query layer for dashboard analytics.

All queries are scoped to a brand_id supplied by the controller via
DashboardFilters.  No query may omit brand_id — this enforces the
strict per-brand tenant isolation required by the spec (§2.3).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status

from app.common.utils.object_id import to_object_id
from app.modules.dashboard.schemas import DashboardFilters
from app.modules.recruitment.enums import (
    INACTIVE_STAGES,
    PIPELINE_ORDER,
    ActivityType,
    PipelineStage,
    PositionStatus,
)
from app.modules.recruitment.models import (
    ActivityLog,
    Candidate,
    Employee,
    Mapping,
    Position,
)

# ── MongoDB operator constants ─────────────────────────────────────────────────
# Defined once here so the aggregation pipelines below don't repeat bare string
# literals, satisfying the python:S1192 (duplicated-literal) lint rule.

_MATCH = "$match"
_GROUP = "$group"
_SORT = "$sort"
_LIMIT = "$limit"
_SKIP = "$skip"
_COUNT = "$count"
_FACET = "$facet"
_LOOKUP = "$lookup"
_ADD_FIELDS = "$addFields"
_UNSET = "$unset"
_COND = "$cond"
_EXPR = "$expr"
_SIZE = "$size"
_FILTER = "$filter"
_TO_STR = "$toString"
_IF_NULL = "$ifNull"
_GT = "$gt"

# Field path constants (frequently referenced across pipelines)
_F_STAGE = "$stage"
_F_STATUS = "$status"
_F_EMPLOYEE_ID = "$employee_id"
_F_POSITION_ID = "$position_id"
_F_EMP_MAPPINGS = "$emp_mappings"
_F_MAPPINGS = "$mappings"
_VAR_M_STAGE = "$$m.stage"
_VAR_CAND_MAPPINGS = "$cand_mappings"

# ── Domain constants ───────────────────────────────────────────────────────────

_ACTIVITY_STAGE_MAP: dict[PipelineStage, ActivityType] = {
    PipelineStage.offer: ActivityType.offer_sent,
    PipelineStage.offer_accepted: ActivityType.offer_accepted,
    PipelineStage.position_close: ActivityType.joined,
    PipelineStage.rejected: ActivityType.rejected,
}


def _humanize_stage(stage: PipelineStage) -> str:
    return stage.value.replace("_", " ").title()


# ── Filter builders ────────────────────────────────────────────────────────────


def _require_brand(filters: DashboardFilters) -> Any:
    """Return the brand_id ObjectId, raising 400 if not present."""
    brand_oid = to_object_id(filters.brand_id, "brand_id")
    if brand_oid is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "brand_id is required")
    return brand_oid


def _date_range(
    field: str, start_date: datetime | None, end_date: datetime | None
) -> dict[str, Any] | None:
    r: dict[str, Any] = {}
    if start_date is not None:
        r["$gte"] = start_date
    if end_date is not None:
        r["$lte"] = end_date
    return {field: r} if r else None


def _base_mapping_match(
    filters: DashboardFilters, *, include_terminal: bool = True
) -> dict[str, Any]:
    brand_oid = _require_brand(filters)
    match: dict[str, Any] = {"brand_id": brand_oid}

    employee_oid = to_object_id(filters.employee_id, "employee_id")
    client_oid = to_object_id(filters.client_id, "client_id")
    if employee_oid is not None:
        match["employee_id"] = employee_oid
    if client_oid is not None:
        match["client_id"] = client_oid

    if filters.pipeline_stage is not None:
        match["stage"] = filters.pipeline_stage.value
    date_match = _date_range("mapped_at", filters.start_date, filters.end_date)
    if date_match is not None:
        match.update(date_match)

    if not include_terminal:
        inactive_values = [s.value for s in INACTIVE_STAGES]
        if filters.pipeline_stage is None:
            match["stage"] = {"$nin": inactive_values}
        elif filters.pipeline_stage.value in inactive_values:
            match["stage"] = {"$in": []}

    return match


def _activity_match(filters: DashboardFilters) -> dict[str, Any]:
    brand_oid = _require_brand(filters)
    match: dict[str, Any] = {"brand_id": brand_oid}

    employee_oid = to_object_id(filters.employee_id, "employee_id")
    if employee_oid is not None:
        match["employee_id"] = employee_oid

    if filters.pipeline_stage is not None:
        activity_type = _ACTIVITY_STAGE_MAP.get(filters.pipeline_stage)
        if activity_type is not None:
            match["activity_type"] = activity_type.value

    date_match = _date_range("created_at", filters.start_date, filters.end_date)
    if date_match is not None:
        match.update(date_match)

    return match


# ── Pagination helper ──────────────────────────────────────────────────────────


def _paginate(page: int, limit: int) -> dict[str, Any]:
    """Return a $facet stage that paginates into items + meta."""
    return {
        _FACET: {
            "items": [{_SKIP: (page - 1) * limit}, {_LIMIT: limit}],
            "meta": [{_COUNT: "total"}],
        }
    }


def _unpack_facet(result: list[Any]) -> tuple[list[Any], int]:
    facet = result[0] if result else {"items": [], "meta": []}
    items = facet.get("items", [])
    total = int(facet.get("meta", [{}])[0].get("total", 0)) if facet.get("meta") else 0
    return items, total


def _stage_filter(input_field: str, stage_value: str) -> dict[str, Any]:
    """Inline $size/$filter combo that counts mappings at a given stage."""
    return {
        _SIZE: {
            _FILTER: {
                "input": input_field,
                "as": "m",
                "cond": {"$eq": [_VAR_M_STAGE, stage_value]},
            }
        }
    }


# ── Aggregations ───────────────────────────────────────────────────────────────


async def fetch_overview(filters: DashboardFilters) -> dict[str, Any]:
    brand_oid = _require_brand(filters)

    pos_match: dict[str, Any] = {"brand_id": brand_oid, "is_active": True}
    client_oid = to_object_id(filters.client_id, "client_id")
    if client_oid is not None:
        pos_match["client_id"] = client_oid
    date_match = _date_range("created_at", filters.start_date, filters.end_date)
    if date_match is not None:
        pos_match.update(date_match)

    job_pipeline = [
        {_MATCH: pos_match},
        {
            _GROUP: {
                "_id": None,
                "open_positions": {"$sum": {_COND: [{"$eq": [_F_STATUS, "open"]}, 1, 0]}},
                "total_seats_open": {"$sum": "$remaining_seats"},
                "seats_filled": {"$sum": "$filled_seats"},
            }
        },
    ]
    job_result = await (await Position.get_motor_collection().aggregate(job_pipeline)).to_list(
        length=None
    )
    job_totals = job_result[0] if job_result else {}

    mapping_match = _base_mapping_match(filters, include_terminal=False)
    mapping_pipeline = [
        {_MATCH: mapping_match},
        {
            _GROUP: {
                "_id": None,
                "candidates_in_pipeline": {"$sum": 1},
                "offers_accepted": {
                    "$sum": {_COND: [{"$eq": [_F_STAGE, PipelineStage.offer_accepted.value]}, 1, 0]}
                },
                "action_needed_count": {
                    "$sum": {
                        _COND: [
                            {
                                "$and": [
                                    {
                                        "$in": [
                                            _F_STAGE,
                                            [
                                                PipelineStage.decision_pending.value,
                                                PipelineStage.offer.value,
                                            ],
                                        ]
                                    },
                                    {"$eq": ["$decision", "pending"]},
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
                "avg_days_to_shortlist": {
                    "$avg": {
                        "$let": {
                            "vars": {
                                "shortlist_event": {
                                    "$first": {
                                        "$sortArray": {
                                            "input": {
                                                "$filter": {
                                                    "input": "$history",
                                                    "as": "h",
                                                    "cond": {
                                                        "$in": [
                                                            "$$h.stage",
                                                            [
                                                                PipelineStage.sent_to_client.value,
                                                                PipelineStage.interview.value,
                                                            ],
                                                        ]
                                                    },
                                                }
                                            },
                                            "sortBy": {"at": 1},
                                        }
                                    }
                                }
                            },
                            "in": {
                                "$cond": [
                                    {"$ne": ["$$shortlist_event", None]},
                                    {
                                        "$divide": [
                                            {
                                                "$dateDiff": {
                                                    "startDate": "$mapped_at",
                                                    "endDate": "$$shortlist_event.at",
                                                    "unit": "millisecond",
                                                }
                                            },
                                            1000 * 60 * 60 * 24,
                                        ]
                                    },
                                    None,
                                ]
                            },
                        }
                    }
                },
            }
        },
    ]
    mapping_result = await (
        await Mapping.get_motor_collection().aggregate(mapping_pipeline)
    ).to_list(length=None)
    mapping_totals = mapping_result[0] if mapping_result else {}

    joined_match = dict(_base_mapping_match(filters, include_terminal=True))
    if filters.pipeline_stage is None:
        joined_match["stage"] = PipelineStage.position_close.value
    joined_pipeline = [
        {_MATCH: joined_match},
        {_GROUP: {"_id": None, "joined_candidates": {"$sum": 1}}},
    ]
    joined_result = await (await Mapping.get_motor_collection().aggregate(joined_pipeline)).to_list(
        length=None
    )
    joined_totals = joined_result[0] if joined_result else {}

    return {
        "summary": {
            "open_positions": int(job_totals.get("open_positions", 0)),
            "total_seats_open": int(job_totals.get("total_seats_open", 0)),
            "seats_filled": int(job_totals.get("seats_filled", 0)),
            "candidates_in_pipeline": int(mapping_totals.get("candidates_in_pipeline", 0)),
            "offers_accepted": int(mapping_totals.get("offers_accepted", 0)),
            "action_needed_count": int(mapping_totals.get("action_needed_count", 0)),
            "avg_days_to_shortlist": round(
                float(mapping_totals.get("avg_days_to_shortlist") or 0.0), 1
            ),
            "joined_candidates": int(joined_totals.get("joined_candidates", 0)),
        }
    }


async def fetch_pipeline(filters: DashboardFilters) -> dict[str, Any]:
    mapping_match = _base_mapping_match(filters, include_terminal=True)
    pipeline = [
        {_MATCH: mapping_match},
        {_GROUP: {"_id": _F_STAGE, "count": {"$sum": 1}}},
    ]
    results = await (await Mapping.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    counts = {PipelineStage(item["_id"]): int(item["count"]) for item in results if item.get("_id")}
    total = sum(counts.values())

    stages: list[dict[str, Any]] = []
    for stage in PIPELINE_ORDER:
        count = counts.get(stage, 0)
        stages.append(
            {
                "stage": stage,
                "label": _humanize_stage(stage),
                "count": count,
                "percent": 0 if total == 0 else round((count / total) * 100, 2),
            }
        )
    return {"stages": stages, "total_candidates": total}
    return {"stages": stages, "total_candidates": total}


async def fetch_sourcing(filters: DashboardFilters) -> dict[str, Any]:
    brand_oid = _require_brand(filters)
    candidate_match: dict[str, Any] = {"brand_id": brand_oid}

    date_match = _date_range("created_at", filters.start_date, filters.end_date)
    if date_match is not None:
        candidate_match.update(date_match)

    pipeline = [
        {_MATCH: candidate_match},
        {
            _LOOKUP: {
                "from": Mapping.Settings.name,
                "localField": "_id",
                "foreignField": "candidate_id",
                "as": "cand_mappings",
            }
        },
        {
            _ADD_FIELDS: {
                "has_mapping": {_COND: [{_GT: [{_SIZE: _VAR_CAND_MAPPINGS}, 0]}, 1, 0]},
                "has_offer": {
                    _COND: [
                        {
                            _GT: [
                                {
                                    _SIZE: {
                                        _FILTER: {
                                            "input": _VAR_CAND_MAPPINGS,
                                            "as": "m",
                                            "cond": {
                                                "$in": [
                                                    "$$m.stage",
                                                    [
                                                        PipelineStage.offer_accepted,
                                                        PipelineStage.joined,
                                                    ],
                                                ]
                                            },
                                        }
                                    }
                                },
                                0,
                            ]
                        },
                        1,
                        0,
                    ]
                },
                "has_joined": {
                    _COND: [
                        {
                            _GT: [
                                {
                                    _SIZE: {
                                        _FILTER: {
                                            "input": _VAR_CAND_MAPPINGS,
                                            "as": "m",
                                            "cond": {"$eq": ["$$m.stage", PipelineStage.joined]},
                                        }
                                    }
                                },
                                0,
                            ]
                        },
                        1,
                        0,
                    ]
                },
            }
        },
        {
            _GROUP: {
                "_id": {"source": "$source", "source_channel": "$source_channel"},
                "candidate_count": {"$sum": 1},
                "pipeline_candidates": {"$sum": "$has_mapping"},
                "offers_accepted": {"$sum": "$has_offer"},
                "joined_candidates": {"$sum": "$has_joined"},
            }
        },
    ]

    # Needs _GT from operators
    results = await (await Candidate.get_motor_collection().aggregate(pipeline)).to_list(
        length=None
    )
    metrics = []
    for item in results:
        _id = item.get("_id", {})
        metrics.append(
            {
                "source_type": _id.get("source"),
                "source_channel": _id.get("source_channel"),
                "candidate_count": item.get("candidate_count", 0),
                "pipeline_candidates": item.get("pipeline_candidates", 0),
                "offers_accepted": item.get("offers_accepted", 0),
                "joined_candidates": item.get("joined_candidates", 0),
            }
        )

    # Sort primarily by candidate count descending
    metrics.sort(key=lambda x: x["candidate_count"], reverse=True)
    return {"metrics": metrics}


async def fetch_employees(filters: DashboardFilters, page: int, limit: int) -> dict[str, Any]:
    brand_oid = _require_brand(filters)
    employee_match: dict[str, Any] = {
        "brand_id": brand_oid,
        "is_active": True,
        "role": {"$nin": ["admin", "maintainer"]},
    }
    employee_oid = to_object_id(filters.employee_id, "employee_id")
    if employee_oid is not None:
        employee_match["_id"] = employee_oid
    date_match = _date_range("created_at", filters.start_date, filters.end_date)
    if date_match is not None:
        employee_match.update(date_match)

    mapping_match = _base_mapping_match(filters, include_terminal=True)
    mapping_lookup: list[dict[str, Any]] = [
        {_MATCH: {_EXPR: {"$eq": [_F_EMPLOYEE_ID, "$$emp_oid"]}}},
    ]
    if mapping_match.get("client_id") is not None:
        mapping_lookup.append({_MATCH: {"client_id": mapping_match["client_id"]}})
    if mapping_match.get("stage") is not None:
        mapping_lookup.append({_MATCH: {"stage": mapping_match["stage"]}})
    if mapping_match.get("mapped_at") is not None:
        mapping_lookup.append({_MATCH: {"mapped_at": mapping_match["mapped_at"]}})

    pipeline = [
        {_MATCH: employee_match},
        {
            _LOOKUP: {
                "from": "candidate_mappings",
                "let": {"emp_oid": "$_id"},
                "pipeline": mapping_lookup,
                "as": "emp_mappings",
            }
        },
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "total_mappings": {_SIZE: _F_EMP_MAPPINGS},
                "mappings": {
                    "offers_sent": _stage_filter(_F_EMP_MAPPINGS, PipelineStage.offer.value),
                    "joined_candidates": _stage_filter(
                        _F_EMP_MAPPINGS, PipelineStage.position_close.value
                    ),
                    "rejected_candidates": _stage_filter(
                        _F_EMP_MAPPINGS, PipelineStage.rejected.value
                    ),
                },
            }
        },
        {_UNSET: ["emp_mappings"]},
        {_SORT: {"created_at": -1, "name": 1}},
        _paginate(page, limit),
    ]
    result = await (await Employee.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    items, total_count = _unpack_facet(result)
    return {"items": items, "total": total_count, "page": page, "limit": limit}


async def fetch_clients(filters: DashboardFilters, page: int, limit: int) -> dict[str, Any]:
    brand_oid = _require_brand(filters)
    pos_match: dict[str, Any] = {"brand_id": brand_oid, "is_active": True}
    client_oid = to_object_id(filters.client_id, "client_id")
    if client_oid is not None:
        pos_match["client_id"] = client_oid
    date_match = _date_range("created_at", filters.start_date, filters.end_date)
    if date_match is not None:
        pos_match.update(date_match)

    mapping_lookup: list[dict[str, Any]] = [
        {_MATCH: {_EXPR: {"$eq": [_F_POSITION_ID, "$$pos_oid"]}}},
    ]
    employee_oid = to_object_id(filters.employee_id, "employee_id")
    if employee_oid is not None:
        mapping_lookup.append({_MATCH: {"employee_id": employee_oid}})
    if filters.pipeline_stage is not None:
        mapping_lookup.append({_MATCH: {"stage": filters.pipeline_stage.value}})

    inactive_values = [s.value for s in INACTIVE_STAGES]
    pipeline = [
        {_MATCH: pos_match},
        {
            _LOOKUP: {
                "from": "candidate_mappings",
                "let": {"pos_oid": "$_id"},
                "pipeline": mapping_lookup,
                "as": "mappings",
            }
        },
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "candidate_count": {_SIZE: _F_MAPPINGS},
                "pipeline_candidates": {
                    _SIZE: {
                        _FILTER: {
                            "input": _F_MAPPINGS,
                            "as": "m",
                            "cond": {"$not": {"$in": [_VAR_M_STAGE, inactive_values]}},
                        }
                    }
                },
                "offers_accepted": _stage_filter(_F_MAPPINGS, PipelineStage.offer_accepted.value),
                "joined_candidates": _stage_filter(_F_MAPPINGS, PipelineStage.position_close.value),
            }
        },
        {_UNSET: ["mappings"]},
        {_SORT: {"created_at": -1, "client_name": 1}},
        _paginate(page, limit),
    ]
    result = await (await Position.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    items, total_count = _unpack_facet(result)
    return {"items": items, "total": total_count, "page": page, "limit": limit}


async def fetch_candidates(filters: DashboardFilters, page: int, limit: int) -> dict[str, Any]:
    brand_oid = _require_brand(filters)
    cand_match: dict[str, Any] = {"brand_id": brand_oid, "is_active": True}
    employee_oid = to_object_id(filters.employee_id, "employee_id")
    client_oid = to_object_id(filters.client_id, "client_id")
    if filters.pipeline_stage is not None:
        cand_match["current_stage"] = filters.pipeline_stage.value
    date_match = _date_range("created_at", filters.start_date, filters.end_date)
    if date_match is not None:
        cand_match.update(date_match)

    agg: list[dict[str, Any]] = [{_MATCH: cand_match}]

    if employee_oid is not None or client_oid is not None:
        mapping_lookup: list[dict[str, Any]] = [
            {_MATCH: {_EXPR: {"$eq": ["$candidate_id", "$$cand_oid"]}}}
        ]
        if employee_oid is not None:
            mapping_lookup.append({_MATCH: {"employee_id": employee_oid}})
        if client_oid is not None:
            mapping_lookup.append({_MATCH: {"client_id": client_oid}})
        agg.extend(
            [
                {
                    _LOOKUP: {
                        "from": "candidate_mappings",
                        "let": {"cand_oid": "$_id"},
                        "pipeline": mapping_lookup,
                        "as": "cand_mappings",
                    }
                },
                {_MATCH: {"cand_mappings": {"$ne": []}}},
                {_UNSET: ["cand_mappings"]},
            ]
        )

    agg.extend(
        [
            {_ADD_FIELDS: {"id": {_TO_STR: "$_id"}}},
            {_SORT: {"created_at": -1, "full_name": 1}},
            _paginate(page, limit),
        ]
    )
    result = await (await Candidate.get_motor_collection().aggregate(agg)).to_list(length=None)
    items, total_count = _unpack_facet(result)
    return {"items": items, "total": total_count, "page": page, "limit": limit}


async def fetch_mappings(filters: DashboardFilters, page: int, limit: int) -> dict[str, Any]:
    mapping_match = _base_mapping_match(filters, include_terminal=True)
    pipeline = [
        {_MATCH: mapping_match},
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "employee_id": {_TO_STR: _F_EMPLOYEE_ID},
                "candidate_id": {_TO_STR: "$candidate_id"},
                "position_id": {_TO_STR: _F_POSITION_ID},
                "job_opening_id": {_TO_STR: _F_POSITION_ID},
                "pipeline_stage": _F_STAGE,
            }
        },
        {_SORT: {"mapped_at": -1, "updated_at": -1}},
        _paginate(page, limit),
    ]
    result = await (await Mapping.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    items, total_count = _unpack_facet(result)
    return {"items": items, "total": total_count, "page": page, "limit": limit}


async def fetch_client_profiles(brand_id: str, page: int, limit: int) -> dict[str, Any]:
    """Aggregate positions grouped by client to produce one row per client.

    Derived status: "active" if ≥1 open position, "on_hold" if none open but
    ≥1 on_hold, "closed" otherwise.  Candidate / recruiter counts come from
    the candidate_mappings collection via lookup.
    """
    brand_oid = to_object_id(brand_id, "brand_id")
    pipeline: list[dict[str, Any]] = [
        {_MATCH: {"is_active": True, "brand_id": brand_oid}},
        {
            _LOOKUP: {
                "from": "candidate_mappings",
                "let": {"pos_oid": "$_id"},
                "pipeline": [{_MATCH: {_EXPR: {"$eq": [_F_POSITION_ID, "$$pos_oid"]}}}],
                "as": "pos_mappings",
            }
        },
        {
            _GROUP: {
                "_id": "$client_id",
                "client_name": {"$first": "$client_name"},
                "total_open_positions": {
                    "$sum": {_COND: [{"$eq": [_F_STATUS, PositionStatus.open.value]}, 1, 0]}
                },
                "total_on_hold": {
                    "$sum": {_COND: [{"$eq": [_F_STATUS, PositionStatus.on_hold.value]}, 1, 0]}
                },
                "candidate_id_arrays": {"$push": "$pos_mappings.candidate_id"},
                "employee_id_arrays": {"$push": "$pos_mappings.employee_id"},
                "last_activity": {"$max": "$updated_at"},
            }
        },
        {
            _ADD_FIELDS: {
                "client_name": "$client_name",
                "all_candidate_ids": {
                    "$reduce": {
                        "input": "$candidate_id_arrays",
                        "initialValue": [],
                        "in": {"$setUnion": ["$$value", "$$this"]},
                    }
                },
                "all_employee_ids": {
                    "$reduce": {
                        "input": "$employee_id_arrays",
                        "initialValue": [],
                        "in": {"$setUnion": ["$$value", "$$this"]},
                    }
                },
                "status": {
                    "$switch": {
                        "branches": [
                            {
                                "case": {"$gt": ["$total_open_positions", 0]},
                                "then": "active",
                            },
                            {
                                "case": {"$gt": ["$total_on_hold", 0]},
                                "then": "on_hold",
                            },
                        ],
                        "default": "closed",
                    }
                },
            }
        },
        {
            "$project": {
                "_id": 0,
                "client_name": 1,
                "total_open_positions": 1,
                "total_candidates": {_SIZE: "$all_candidate_ids"},
                "active_recruiters": {_SIZE: "$all_employee_ids"},
                "last_activity": 1,
                "status": 1,
            }
        },
        {_SORT: {"last_activity": -1, "client_name": 1}},
        _paginate(page, limit),
    ]
    result = await (await Position.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    items, total = _unpack_facet(result)
    return {"items": items, "total": total, "page": page, "limit": limit}


async def fetch_activities(filters: DashboardFilters, page: int, limit: int) -> dict[str, Any]:
    activity_match = _activity_match(filters)
    pipeline = [
        {_MATCH: activity_match},
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "employee_id": {
                    _COND: [
                        {_IF_NULL: [_F_EMPLOYEE_ID, False]},
                        {_TO_STR: _F_EMPLOYEE_ID},
                        None,
                    ]
                },
            }
        },
        {_SORT: {"created_at": -1}},
        _paginate(page, limit),
    ]
    result = await (await ActivityLog.get_motor_collection().aggregate(pipeline)).to_list(
        length=None
    )
    items, total_count = _unpack_facet(result)
    return {"items": items, "total": total_count, "page": page, "limit": limit}

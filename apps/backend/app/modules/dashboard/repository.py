"""MongoDB query layer for dashboard analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status

from app.common.utils.object_id import to_object_id
from app.modules.dashboard.enums import ActivityType, JobStatus, PipelineStage, TargetEntityType
from app.modules.dashboard.models import (
    ActivityLog,
    CandidateMapping,
    DashboardCandidate,
    DashboardEmployee,
    JobOpening,
)
from app.modules.dashboard.schemas import DashboardFilters

_TERMINAL_STAGES = {PipelineStage.joined, PipelineStage.rejected, PipelineStage.dropped, PipelineStage.hold}
_PIPELINE_ORDER = [
    PipelineStage.added,
    PipelineStage.shortlisted,
    PipelineStage.sent_to_client,
    PipelineStage.rejected,
    PipelineStage.hold,
    PipelineStage.offer_sent,
    PipelineStage.offer_accepted,
    PipelineStage.joined,
    PipelineStage.dropped,
]
_ACTIVITY_STAGE_MAP = {
    PipelineStage.offer_sent: ActivityType.offer_sent,
    PipelineStage.offer_accepted: ActivityType.offer_accepted,
    PipelineStage.joined: ActivityType.joined,
    PipelineStage.rejected: ActivityType.rejected,
}


def _humanize_stage(stage: PipelineStage) -> str:
    return stage.value.replace("_", " ").title()


def _date_range(field: str, start_date: datetime | None, end_date: datetime | None) -> dict[str, Any] | None:
    range_match: dict[str, Any] = {}
    if start_date is not None:
        range_match["$gte"] = start_date
    if end_date is not None:
        range_match["$lte"] = end_date
    if not range_match:
        return None
    return {field: range_match}


def _base_mapping_match(filters: DashboardFilters, *, include_terminal: bool = True) -> dict[str, Any]:
    match: dict[str, Any] = {}

    employee_oid = to_object_id(filters.employee_id, "employee_id")
    client_oid = to_object_id(filters.client_id, "client_id")
    if employee_oid is not None:
        match["employee_id"] = employee_oid
    if client_oid is not None:
        match["job_opening_id"] = client_oid
    if filters.pipeline_stage is not None:
        match["pipeline_stage"] = filters.pipeline_stage.value
    range_match = _date_range("mapped_at", filters.start_date, filters.end_date)
    if range_match is not None:
        match.update(range_match)

    if not include_terminal:
        terminal_values = [stage.value for stage in _TERMINAL_STAGES]
        if filters.pipeline_stage is None:
            match["pipeline_stage"] = {"$nin": terminal_values}
        elif filters.pipeline_stage.value in terminal_values:
            match["pipeline_stage"] = {"$in": []}
        else:
            match["pipeline_stage"] = filters.pipeline_stage.value

    return match


def _activity_match(filters: DashboardFilters) -> dict[str, Any]:
    match: dict[str, Any] = {}

    employee_oid = to_object_id(filters.employee_id, "employee_id")
    client_oid = to_object_id(filters.client_id, "client_id")
    if employee_oid is not None:
        match["employee_id"] = employee_oid
    if client_oid is not None:
        match["$or"] = [
            {"target_entity_type": TargetEntityType.client, "target_entity_id": filters.client_id},
            {"target_entity_type": TargetEntityType.job_opening, "target_entity_id": filters.client_id},
        ]

    if filters.pipeline_stage is not None:
        activity_type = _ACTIVITY_STAGE_MAP.get(filters.pipeline_stage)
        if activity_type is not None:
            match["activity_type"] = activity_type.value
    range_match = _date_range("created_at", filters.start_date, filters.end_date)
    if range_match is not None:
        match.update(range_match)

    return match


async def fetch_overview(filters: DashboardFilters) -> dict[str, Any]:
    job_match: dict[str, Any] = {"is_active": True}
    client_oid = to_object_id(filters.client_id, "client_id")
    if client_oid is not None:
        job_match["_id"] = client_oid

    job_date_match = _date_range("created_at", filters.start_date, filters.end_date)
    if job_date_match is not None:
        job_match.update(job_date_match)

    job_pipeline = [
        {"$match": job_match},
        {
            "$group": {
                "_id": None,
                "open_positions": {
                    "$sum": {"$cond": [{"$eq": ["$status", JobStatus.open.value]}, 1, 0]}
                },
                "total_seats_open": {"$sum": "$remaining_seats"},
                "seats_filled": {"$sum": "$filled_seats"},
            }
        },
    ]
    job_result = await (await JobOpening.get_motor_collection().aggregate(job_pipeline)).to_list(length=None)
    job_totals = job_result[0] if job_result else {}

    mapping_match = _base_mapping_match(filters, include_terminal=False)
    mapping_pipeline = [
        {"$match": mapping_match},
        {
            "$group": {
                "_id": None,
                "candidates_in_pipeline": {"$sum": 1},
                "offers_accepted": {
                    "$sum": {"$cond": [{"$eq": ["$pipeline_stage", PipelineStage.offer_accepted.value]}, 1, 0]}
                },
            }
        },
    ]
    mapping_result = await (await CandidateMapping.get_motor_collection().aggregate(mapping_pipeline)).to_list(length=None)
    mapping_totals = mapping_result[0] if mapping_result else {}

    joined_match = dict(_base_mapping_match(filters, include_terminal=True))
    if filters.pipeline_stage is None:
        joined_match["pipeline_stage"] = PipelineStage.joined.value
    joined_pipeline = [
        {"$match": joined_match},
        {"$group": {"_id": None, "joined_candidates": {"$sum": 1}}},
    ]
    joined_result = await (await CandidateMapping.get_motor_collection().aggregate(joined_pipeline)).to_list(length=None)
    joined_totals = joined_result[0] if joined_result else {}

    return {
        "summary": {
            "open_positions": int(job_totals.get("open_positions", 0)),
            "total_seats_open": int(job_totals.get("total_seats_open", 0)),
            "seats_filled": int(job_totals.get("seats_filled", 0)),
            "candidates_in_pipeline": int(mapping_totals.get("candidates_in_pipeline", 0)),
            "offers_accepted": int(mapping_totals.get("offers_accepted", 0)),
            "joined_candidates": int(joined_totals.get("joined_candidates", 0)),
        }
    }


async def fetch_pipeline(filters: DashboardFilters) -> dict[str, Any]:
    mapping_match = _base_mapping_match(filters, include_terminal=True)
    pipeline = [
        {"$match": mapping_match},
        {
            "$group": {
                "_id": "$pipeline_stage",
                "count": {"$sum": 1},
            }
        },
    ]
    results = await (await CandidateMapping.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    counts = {PipelineStage(item["_id"]): int(item["count"]) for item in results if item.get("_id")}
    total_candidates = sum(counts.values())

    stages: list[dict[str, Any]] = []
    for stage in _PIPELINE_ORDER:
        count = counts.get(stage, 0)
        stages.append(
            {
                "stage": stage,
                "label": _humanize_stage(stage),
                "count": count,
                "percent": 0 if total_candidates == 0 else round((count / total_candidates) * 100, 2),
            }
        )

    return {"stages": stages, "total_candidates": total_candidates}


async def fetch_employees(filters: DashboardFilters, page: int, limit: int) -> dict[str, Any]:
    employee_match: dict[str, Any] = {"is_active": True}
    employee_oid = to_object_id(filters.employee_id, "employee_id")
    if employee_oid is not None:
        employee_match["_id"] = employee_oid

    date_match = _date_range("created_at", filters.start_date, filters.end_date)
    if date_match is not None:
        employee_match.update(date_match)

    mapping_match = _base_mapping_match(filters, include_terminal=True)
    mapping_lookup_pipeline: list[dict[str, Any]] = [
        {"$match": {"$expr": {"$eq": ["$employee_id", "$$employee_oid"]}}},
    ]
    if mapping_match.get("job_opening_id") is not None:
        mapping_lookup_pipeline.append({"$match": {"job_opening_id": mapping_match["job_opening_id"]}})
    if mapping_match.get("pipeline_stage") is not None:
        mapping_lookup_pipeline.append({"$match": {"pipeline_stage": mapping_match["pipeline_stage"]}})
    if mapping_match.get("mapped_at") is not None:
        mapping_lookup_pipeline.append({"$match": {"mapped_at": mapping_match["mapped_at"]}})

    pipeline = [
        {"$match": employee_match},
        {
            "$lookup": {
                "from": "candidate_mappings",
                "let": {"employee_oid": "$_id"},
                "pipeline": mapping_lookup_pipeline,
                "as": "employee_mappings",
            }
        },
        {
            "$addFields": {
                "id": {"$toString": "$_id"},
                "total_mappings": {"$size": "$employee_mappings"},
                "mappings": {
                    "offers_sent": {
                        "$size": {
                            "$filter": {
                                "input": "$employee_mappings",
                                "as": "mapping",
                                "cond": {"$eq": ["$$mapping.pipeline_stage", PipelineStage.offer_sent.value]},
                            }
                        }
                    },
                    "joined_candidates": {
                        "$size": {
                            "$filter": {
                                "input": "$employee_mappings",
                                "as": "mapping",
                                "cond": {"$eq": ["$$mapping.pipeline_stage", PipelineStage.joined.value]},
                            }
                        }
                    },
                    "rejected_candidates": {
                        "$size": {
                            "$filter": {
                                "input": "$employee_mappings",
                                "as": "mapping",
                                "cond": {"$eq": ["$$mapping.pipeline_stage", PipelineStage.rejected.value]},
                            }
                        }
                    },
                },
            }
        },
        {"$unset": ["employee_mappings"]},
        {"$sort": {"created_at": -1, "name": 1}},
        {
            "$facet": {
                "items": [{"$skip": (page - 1) * limit}, {"$limit": limit}],
                "meta": [{"$count": "total"}],
            }
        },
    ]
    result = await (await DashboardEmployee.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    facet = result[0] if result else {"items": [], "meta": []}
    items = facet.get("items", [])
    total = int(facet.get("meta", [{}])[0].get("total", 0)) if facet.get("meta") else 0
    return {"items": items, "total": total, "page": page, "limit": limit}


async def fetch_clients(filters: DashboardFilters, page: int, limit: int) -> dict[str, Any]:
    job_match: dict[str, Any] = {"is_active": True}
    client_oid = to_object_id(filters.client_id, "client_id")
    if client_oid is not None:
        job_match["_id"] = client_oid

    date_match = _date_range("created_at", filters.start_date, filters.end_date)
    if date_match is not None:
        job_match.update(date_match)

    mapping_lookup_pipeline = [
        {"$match": {"$expr": {"$eq": ["$job_opening_id", "$$job_oid"]}}},
    ]
    employee_oid = to_object_id(filters.employee_id, "employee_id")
    if employee_oid is not None:
        mapping_lookup_pipeline.append({"$match": {"employee_id": employee_oid}})
    if filters.pipeline_stage is not None:
        mapping_lookup_pipeline.append({"$match": {"pipeline_stage": filters.pipeline_stage.value}})
    pipeline = [
        {"$match": job_match},
        {
            "$lookup": {
                "from": "candidate_mappings",
                "let": {"job_oid": "$_id"},
                "pipeline": mapping_lookup_pipeline,
                "as": "mappings",
            }
        },
        {
            "$addFields": {
                "id": {"$toString": "$_id"},
                "candidate_count": {"$size": "$mappings"},
                "pipeline_candidates": {
                    "$size": {
                        "$filter": {
                            "input": "$mappings",
                            "as": "mapping",
                            "cond": {
                                "$not": {
                                    "$in": [
                                        "$$mapping.pipeline_stage",
                                        [stage.value for stage in _TERMINAL_STAGES],
                                    ]
                                }
                            },
                        }
                    }
                },
                "offers_accepted": {
                    "$size": {
                        "$filter": {
                            "input": "$mappings",
                            "as": "mapping",
                            "cond": {"$eq": ["$$mapping.pipeline_stage", PipelineStage.offer_accepted.value]},
                        }
                    }
                },
                "joined_candidates": {
                    "$size": {
                        "$filter": {
                            "input": "$mappings",
                            "as": "mapping",
                            "cond": {"$eq": ["$$mapping.pipeline_stage", PipelineStage.joined.value]},
                        }
                    }
                },
            }
        },
        {"$unset": ["mappings"]},
        {"$sort": {"created_at": -1, "client_name": 1}},
        {
            "$facet": {
                "items": [{"$skip": (page - 1) * limit}, {"$limit": limit}],
                "meta": [{"$count": "total"}],
            }
        },
    ]
    result = await (await JobOpening.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    facet = result[0] if result else {"items": [], "meta": []}
    items = facet.get("items", [])
    total = int(facet.get("meta", [{}])[0].get("total", 0)) if facet.get("meta") else 0
    return {"items": items, "total": total, "page": page, "limit": limit}


async def fetch_candidates(filters: DashboardFilters, page: int, limit: int) -> dict[str, Any]:
    candidate_match: dict[str, Any] = {"is_active": True}
    employee_oid = to_object_id(filters.employee_id, "employee_id")
    client_oid = to_object_id(filters.client_id, "client_id")
    if filters.pipeline_stage is not None:
        candidate_match["current_stage"] = filters.pipeline_stage.value
    date_match = _date_range("created_at", filters.start_date, filters.end_date)
    if date_match is not None:
        candidate_match.update(date_match)

    pipeline: list[dict[str, Any]] = [{"$match": candidate_match}]

    if employee_oid is not None or client_oid is not None:
        mapping_lookup_pipeline = [{"$match": {"$expr": {"$eq": ["$candidate_id", "$$candidate_oid"]}}}]
        if employee_oid is not None:
            mapping_lookup_pipeline.append({"$match": {"employee_id": employee_oid}})
        if client_oid is not None:
            mapping_lookup_pipeline.append({"$match": {"job_opening_id": client_oid}})

        pipeline.extend(
            [
                {
                    "$lookup": {
                        "from": "candidate_mappings",
                        "let": {"candidate_oid": "$_id"},
                        "pipeline": mapping_lookup_pipeline,
                        "as": "candidate_mappings",
                    }
                },
                {"$match": {"candidate_mappings": {"$ne": []}}},
                {"$unset": ["candidate_mappings"]},
            ]
        )

    pipeline.extend(
        [
            {"$addFields": {"id": {"$toString": "$_id"}}},
            {"$sort": {"created_at": -1, "full_name": 1}},
            {
                "$facet": {
                    "items": [{"$skip": (page - 1) * limit}, {"$limit": limit}],
                    "meta": [{"$count": "total"}],
                }
            },
        ]
    )
    result = await (await DashboardCandidate.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    facet = result[0] if result else {"items": [], "meta": []}
    items = facet.get("items", [])
    total = int(facet.get("meta", [{}])[0].get("total", 0)) if facet.get("meta") else 0
    return {"items": items, "total": total, "page": page, "limit": limit}


async def fetch_mappings(filters: DashboardFilters, page: int, limit: int) -> dict[str, Any]:
    mapping_match = _base_mapping_match(filters, include_terminal=True)
    pipeline = [
        {"$match": mapping_match},
        {
            "$addFields": {
                "id": {"$toString": "$_id"},
                "employee_id": {"$toString": "$employee_id"},
                "candidate_id": {"$toString": "$candidate_id"},
                "job_opening_id": {"$toString": "$job_opening_id"},
            }
        },
        {"$sort": {"mapped_at": -1, "updated_at": -1}},
        {
            "$facet": {
                "items": [{"$skip": (page - 1) * limit}, {"$limit": limit}],
                "meta": [{"$count": "total"}],
            }
        },
    ]
    result = await (await CandidateMapping.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    facet = result[0] if result else {"items": [], "meta": []}
    items = facet.get("items", [])
    total = int(facet.get("meta", [{}])[0].get("total", 0)) if facet.get("meta") else 0
    return {"items": items, "total": total, "page": page, "limit": limit}


async def fetch_activities(filters: DashboardFilters, page: int, limit: int) -> dict[str, Any]:
    activity_match = _activity_match(filters)
    pipeline = [
        {"$match": activity_match},
        {
            "$addFields": {
                "id": {"$toString": "$_id"},
                "employee_id": {"$cond": [{"$ifNull": ["$employee_id", False]}, {"$toString": "$employee_id"}, None]},
            }
        },
        {"$sort": {"created_at": -1}},
        {
            "$facet": {
                "items": [{"$skip": (page - 1) * limit}, {"$limit": limit}],
                "meta": [{"$count": "total"}],
            }
        },
    ]
    result = await (await ActivityLog.get_motor_collection().aggregate(pipeline)).to_list(length=None)
    facet = result[0] if result else {"items": [], "meta": []}
    items = facet.get("items", [])
    total = int(facet.get("meta", [{}])[0].get("total", 0)) if facet.get("meta") else 0
    return {"items": items, "total": total, "page": page, "limit": limit}


async def create_activity_log(
    *,
    employee_id: str | None,
    activity_type: ActivityType,
    target_entity_type: TargetEntityType,
    target_entity_id: str,
    description: str,
) -> ActivityLog:
    activity = ActivityLog(
        employee_id=to_object_id(employee_id, "employee_id"),
        activity_type=activity_type,
        target_entity_type=target_entity_type,
        target_entity_id=target_entity_id,
        description=description,
    )
    await activity.insert()
    return activity


async def create_candidate_mapping(
    *,
    employee_id: str,
    candidate_id: str,
    job_opening_id: str,
    pipeline_stage: PipelineStage,
) -> CandidateMapping:
    candidate_oid = to_object_id(candidate_id, "candidate_id")
    job_opening_oid = to_object_id(job_opening_id, "job_opening_id")
    existing = await CandidateMapping.find_one(
        CandidateMapping.candidate_id == candidate_oid,
        CandidateMapping.job_opening_id == job_opening_oid,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate is already mapped to this job opening",
        )

    mapping = CandidateMapping(
        employee_id=to_object_id(employee_id, "employee_id"),
        candidate_id=candidate_oid,
        job_opening_id=job_opening_oid,
        pipeline_stage=pipeline_stage,
    )
    await mapping.insert()
    return mapping

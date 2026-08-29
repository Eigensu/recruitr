"""Activity log API — maintainer/admin only.

Endpoints:
  GET /activity   paginated feed of all recruitment activities for the brand
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.common.dtos.pagination import PaginationMeta
from app.dependencies import get_tenant, require_maintainer
from app.modules.recruitment.models import ActivityLog
from app.modules.recruitment.schemas import TenantScope

router = APIRouter()

_Tenant = Annotated[TenantScope, Depends(get_tenant)]
_Page = Annotated[int, Query(ge=1)]
_Limit = Annotated[int, Query(ge=1, le=100)]

_MATCH = "$match"
_LOOKUP = "$lookup"
_ADD_FIELDS = "$addFields"
_UNSET = "$unset"
_SORT = "$sort"
_FACET = "$facet"
_SKIP = "$skip"
_LIMIT_OP = "$limit"
_COUNT = "$count"
_TO_STR = "$toString"
_EXPR = "$expr"
_IF_NULL = "$ifNull"


class ActivityItem(BaseModel):
    id: str
    activity_type: str
    description: str
    target_entity_type: str
    target_entity_id: str
    employee_id: str | None = None
    employee_name: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class ActivityPage(BaseModel):
    items: list[ActivityItem]
    meta: PaginationMeta


@router.get("")
async def list_activity(
    tenant: _Tenant,
    _: Annotated[object, Depends(require_maintainer)],
    page: _Page = 1,
    limit: _Limit = 50,
    search: Annotated[str | None, Query()] = None,
    activityType: Annotated[str | None, Query()] = None,
    recruiterId: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
) -> ActivityPage:
    match: dict = {"brand_id": tenant.brand_id}
    if activityType:
        match["activity_type"] = activityType
    if category:
        match["target_entity_type"] = category
    if recruiterId:
        from bson import ObjectId

        try:
            match["employee_id"] = ObjectId(recruiterId)
        except Exception:
            match["employee_id"] = recruiterId

    pipeline = [
        {_MATCH: match},
        {
            _LOOKUP: {
                "from": "employees",
                "let": {"emp_id": "$employee_id"},
                "pipeline": [
                    {
                        _MATCH: {
                            _EXPR: {
                                "$and": [
                                    {"$ne": ["$$emp_id", None]},
                                    {"$eq": ["$_id", "$$emp_id"]},
                                ]
                            }
                        }
                    },
                    {"$project": {"name": 1}},
                ],
                "as": "_emp",
            }
        },
        {
            _ADD_FIELDS: {
                "id": {_TO_STR: "$_id"},
                "employee_id": {
                    "$cond": [
                        {_IF_NULL: ["$employee_id", False]},
                        {_TO_STR: "$employee_id"},
                        None,
                    ]
                },
                "employee_name": {_IF_NULL: [{"$first": "$_emp.name"}, None]},
                "created_at": {
                    "$dateToString": {"format": "%Y-%m-%dT%H:%M:%SZ", "date": "$created_at"}
                },
            }
        },
        {_UNSET: ["_emp", "_id"]},
    ]

    if search:
        pipeline.append(
            {
                "$match": {
                    "$or": [
                        {"description": {"$regex": search, "$options": "i"}},
                        {"employee_name": {"$regex": search, "$options": "i"}},
                        {"activity_type": {"$regex": search, "$options": "i"}},
                    ]
                }
            }
        )

    pipeline.extend(
        [
            {_SORT: {"created_at": -1}},
            {
                _FACET: {
                    "items": [{_SKIP: (page - 1) * limit}, {_LIMIT_OP: limit}],
                    "meta": [{_COUNT: "total"}],
                }
            },
        ]
    )

    result = await (await ActivityLog.get_motor_collection().aggregate(pipeline)).to_list(
        length=None
    )  # type: ignore[misc]
    facet = result[0] if result else {"items": [], "meta": []}
    items = facet.get("items", [])
    total = int(facet.get("meta", [{}])[0].get("total", 0)) if facet.get("meta") else 0
    pages = 0 if total == 0 else (total + limit - 1) // limit

    meta = PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )
    return ActivityPage(items=[ActivityItem.model_validate(i) for i in items], meta=meta)

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import (
    get_tenant,
    get_viewer,
    require_maintainer,
)
from app.modules.auth.models import User
from app.modules.recruitment.models import (
    ActivityLog,
    Employee,
    RecruitmentTask,
    TaskAssignmentType,
    Team,
)
from app.modules.recruitment.schemas.shared import TenantScope
from app.modules.recruitment.schemas.tasks import (
    RecruiterProgress,
    TaskCreate,
    TaskResponse,
)

router = APIRouter()
_Tenant = Depends(get_tenant)
_Admin = Depends(require_maintainer)
_Viewer = Depends(get_viewer)


def _to_object_id(val: str, field_name: str) -> PydanticObjectId:
    try:
        return PydanticObjectId(val)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid {field_name}") from None


async def _calculate_progress(
    brand_id: PydanticObjectId, employee_id: PydanticObjectId, task: RecruitmentTask
) -> int:
    """Calculate actual progress for one employee."""
    return await ActivityLog.find(
        ActivityLog.brand_id == brand_id,
        ActivityLog.employee_id == employee_id,
        ActivityLog.activity_type == task.tracked_activity_type,
        ActivityLog.created_at >= task.start_date,
        ActivityLog.created_at <= task.due_date,
    ).count()


@router.post("/", response_model=TaskResponse)
async def create_task(
    payload: TaskCreate, tenant: TenantScope = _Tenant, _: User = _Admin
) -> TaskResponse:
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing payload")

    assignee_oid = None
    if payload.assignee_type in [TaskAssignmentType.single, TaskAssignmentType.team]:
        if not payload.assignee_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "assignee_id required")
        assignee_oid = _to_object_id(payload.assignee_id, "assignee_id")

        # Verify exists
        if payload.assignee_type == TaskAssignmentType.single:
            if not await Employee.find_one({"_id": assignee_oid, "brand_id": tenant.brand_id}):
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
        elif payload.assignee_type == TaskAssignmentType.team and not await Team.find_one(
            {"_id": assignee_oid, "brand_id": tenant.brand_id}
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")

    task = RecruitmentTask(
        brand_id=tenant.brand_id,
        title=payload.title,
        description=payload.description,
        tracked_activity_type=payload.tracked_activity_type,
        target_count=payload.target_count,
        assignee_type=payload.assignee_type,
        assignee_id=assignee_oid,
        start_date=payload.start_date,
        due_date=payload.due_date,
    )
    await task.insert()

    return TaskResponse(
        id=str(task.id),
        title=task.title,
        description=task.description,
        tracked_activity_type=task.tracked_activity_type,
        target_count=task.target_count,
        assignee_type=task.assignee_type,
        assignee_id=str(task.assignee_id) if task.assignee_id else None,
        start_date=task.start_date,
        due_date=task.due_date,
        is_active=task.is_active,
        created_at=task.created_at,
    )


@router.get("/", response_model=list[TaskResponse])
async def list_tasks(tenant: TenantScope = _Tenant, viewer: User = _Viewer) -> list[TaskResponse]:
    # If admin, fetch all active tasks in brand
    is_admin = viewer.role in ("admin", "maintainer")

    query = {"brand_id": tenant.brand_id, "is_active": True}

    if not is_admin:
        if not tenant.employee_id:
            return []

        emp = await Employee.find_one({"_id": tenant.employee_id})
        if not emp:
            return []

        or_conds = [
            {"assignee_type": TaskAssignmentType.all},
            {"assignee_type": TaskAssignmentType.single, "assignee_id": tenant.employee_id},
        ]
        if emp.team_id:
            or_conds.append({"assignee_type": TaskAssignmentType.team, "assignee_id": emp.team_id})

        query["$or"] = or_conds

    tasks = await RecruitmentTask.find(query).to_list()
    responses = []

    for task in tasks:
        # Compute progress
        base_resp = TaskResponse(
            id=str(task.id),
            title=task.title,
            description=task.description,
            tracked_activity_type=task.tracked_activity_type,
            target_count=task.target_count,
            assignee_type=task.assignee_type,
            assignee_id=str(task.assignee_id) if task.assignee_id else None,
            start_date=task.start_date,
            due_date=task.due_date,
            is_active=task.is_active,
            created_at=task.created_at,
        )

        if not is_admin:
            # Recruiter view - just their own progress
            completed = await _calculate_progress(tenant.brand_id, tenant.employee_id, task)
            base_resp.completed_count = min(completed, task.target_count)
            base_resp.progress_percentage = int(
                (base_resp.completed_count / task.target_count) * 100
            )
            responses.append(base_resp)
        else:
            # Admin view
            if task.assignee_type == TaskAssignmentType.single:
                emp = await Employee.find_one({"_id": task.assignee_id})
                if emp:
                    completed = await _calculate_progress(tenant.brand_id, task.assignee_id, task)
                    base_resp.completed_count = min(completed, task.target_count)
                    base_resp.progress_percentage = int(
                        (base_resp.completed_count / task.target_count) * 100
                    )
                    base_resp.detailed_progress = [
                        RecruiterProgress(
                            employee_id=str(emp.id),
                            name=emp.name,
                            completed_count=base_resp.completed_count,
                            progress_percentage=base_resp.progress_percentage,
                        )
                    ]
            else:
                # Team or All
                emp_query = {
                    "brand_id": tenant.brand_id,
                    "is_active": True,
                    "role": {"$nin": ["admin", "maintainer"]},
                }
                if task.assignee_type == TaskAssignmentType.team:
                    emp_query["team_id"] = task.assignee_id

                emps = await Employee.find(emp_query).to_list()
                detailed = []
                for emp in emps:
                    completed = await _calculate_progress(tenant.brand_id, emp.id, task)
                    completed = min(completed, task.target_count)
                    pct = int((completed / task.target_count) * 100)
                    detailed.append(
                        RecruiterProgress(
                            employee_id=str(emp.id),
                            name=emp.name,
                            completed_count=completed,
                            progress_percentage=pct,
                        )
                    )

                # Average progress
                if detailed:
                    total_pct = sum(d.progress_percentage for d in detailed)
                    total_completed = sum(d.completed_count for d in detailed)
                    base_resp.progress_percentage = int(total_pct / len(detailed))
                    base_resp.completed_count = total_completed

                base_resp.detailed_progress = detailed

            responses.append(base_resp)

    return responses


@router.delete("/{task_id}")
async def delete_task(task_id: str, tenant: TenantScope = _Tenant, _: User = _Admin) -> dict:
    tid = _to_object_id(task_id, "task_id")
    task = await RecruitmentTask.find_one({"_id": tid, "brand_id": tenant.brand_id})
    if not task:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    await task.delete()
    return {"status": "ok"}

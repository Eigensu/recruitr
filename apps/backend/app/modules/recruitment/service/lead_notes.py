"""Screening notes: what each person who screened a lead wrote, at their own stage.

A permanent, append-only log (`LeadNote`), so a recruiter opening a candidate can
read what the telecaller and the reviewer thought before ever speaking to them.
It sits beside `intake_service` rather than inside it, the direction
`cv_requests` and `resume_service` started: import it by module path.
"""

from __future__ import annotations

from beanie import PydanticObjectId

from app.modules.recruitment.enums import IntakeLeadStatus, IntakeNoteStage
from app.modules.recruitment.models import Employee, IntakeLead, LeadNote
from app.modules.recruitment.schemas import TenantScope

# Where a lead is, mapped to whose step that is. A telecaller's reject keeps the
# lead at the telecaller's stage: it never reached anyone else.
_STAGE_BY_STATUS: dict[IntakeLeadStatus, IntakeNoteStage] = {
    IntakeLeadStatus.pending_telecaller: IntakeNoteStage.telecaller,
    IntakeLeadStatus.unassigned: IntakeNoteStage.telecaller,
    IntakeLeadStatus.rejected: IntakeNoteStage.telecaller,
    IntakeLeadStatus.duplicate: IntakeNoteStage.telecaller,
    IntakeLeadStatus.pending_review: IntakeNoteStage.review,
    IntakeLeadStatus.pending_recruiter: IntakeNoteStage.recruiter,
    IntakeLeadStatus.actioned: IntakeNoteStage.recruiter,
    IntakeLeadStatus.archived: IntakeNoteStage.recruiter,
}


def stage_for(lead: IntakeLead) -> IntakeNoteStage:
    """Whose stage the lead is at right now, which is the stage a new note gets."""
    return _STAGE_BY_STATUS[lead.status]


async def add_note(lead: IntakeLead, *, author: TenantScope, body: str) -> LeadNote:
    """Append a note to the lead, stamped with the stage it is at and who wrote it.

    The author's name and role are copied onto the row, so the history reads the
    same after they are renamed, change role or are removed.
    """
    employee = await Employee.get(author.employee_id) if author.employee_id else None
    note = LeadNote(
        brand_id=lead.brand_id,
        lead_id=lead.id,
        candidate_id=lead.candidate_id,
        stage=stage_for(lead),
        body=body,
        author_id=author.employee_id,
        author_name=employee.name if employee else None,
        author_role=author.role.value if author.role else None,
    )
    await note.insert()
    return note


def to_response(note: LeadNote, *, candidate_name: str | None = None) -> dict:
    """A note as the API shows it (ids as strings)."""
    return {
        "id": str(note.id),
        "lead_id": str(note.lead_id),
        "candidate_id": str(note.candidate_id),
        "stage": note.stage,
        "body": note.body,
        "author_id": str(note.author_id),
        "author_name": note.author_name,
        "author_role": note.author_role,
        "created_at": note.created_at,
        "candidate_name": candidate_name,
    }


async def notes_for_lead(
    brand_id: PydanticObjectId,
    lead_id: PydanticObjectId,
    *,
    stages: set[IntakeNoteStage] | None = None,
) -> list[LeadNote]:
    """A lead's notes, oldest first; only `stages` of them when given."""
    match: dict = {"brand_id": brand_id, "lead_id": lead_id}
    if stages is not None:
        match["stage"] = {"$in": [s.value for s in stages]}
    return await LeadNote.find(match).sort("created_at").to_list()


async def notes_for_candidate(
    brand_id: PydanticObjectId, candidate_id: PydanticObjectId
) -> list[LeadNote]:
    """Every note on a candidate across all their leads, oldest first."""
    return (
        await LeadNote.find({"brand_id": brand_id, "candidate_id": candidate_id})
        .sort("created_at")
        .to_list()
    )

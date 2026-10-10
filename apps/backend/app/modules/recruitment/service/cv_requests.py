"""CV upload links: asking a lead's candidate for their CV.

Most leads arrive with no CV — a Meta lead-ad form does not ask for one — so
whoever holds the lead makes a link here and sends it to the candidate
themselves, on WhatsApp or however they reach them. The candidate opens it with
no account and uploads their CV, which lands on their record exactly as a staff
upload would (`build_candidate_resume_update`), and so shows on the Review tab
card and in the candidate drawer. Nothing waits on it: the lead moves on with
or without a CV.

    issue_link(lead, actor_id)   a fresh link, cancelling the lead's previous one
    lead_for_token(token)        the lead a live link belongs to, or None
    attach_cv(lead, ...)         store an upload and tell whoever holds the lead

Only a SHA-256 of the token is stored: the link is the credential, and a
database read must not hand out working ones. Keeping it on the lead rather
than in a collection of links is what makes a new link cancel the old — there
is one hash per lead, and issuing overwrites it. A link works for CV_LINK_TTL,
for as many uploads as the candidate needs, each replacing the last, so someone
who sent the wrong file can send the right one.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from beanie import PydanticObjectId

from app.modules.recruitment.enums import CandidateEventType, IntakeLeadStatus, NotificationKind
from app.modules.recruitment.models import Candidate, IntakeLead, Notification
from app.modules.recruitment.repository import record_candidate_event
from app.modules.recruitment.schemas import TenantScope
from app.modules.recruitment.service.intake_service import as_utc
from app.modules.recruitment.service.resume_service import build_candidate_resume_update
from app.modules.recruitment.utils.resume_parser import ParsedResume

CV_LINK_TTL = timedelta(days=7)

# Leads with someone still to decide on them. A link on a rejected or archived
# lead would only attach a CV to a candidate nobody is looking at any more.
REQUESTABLE_STATUSES = (
    IntakeLeadStatus.unassigned,
    IntakeLeadStatus.pending_telecaller,
    IntakeLeadStatus.pending_review,
    IntakeLeadStatus.pending_recruiter,
)
_CLOSED_STATUSES = (IntakeLeadStatus.rejected, IntakeLeadStatus.archived)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def issue_link(
    lead: IntakeLead, *, actor_id: PydanticObjectId | None, now: datetime | None = None
) -> tuple[str, datetime]:
    """A new link for this lead's candidate: (token, when it stops working)."""
    stamp = now or datetime.now(UTC)
    token = secrets.token_urlsafe(32)
    expires_at = stamp + CV_LINK_TTL
    await IntakeLead.find_one({"_id": lead.id}).update(
        {
            "$set": {
                "cv_upload_token_hash": _digest(token),
                "cv_upload_expires_at": expires_at,
                "cv_upload_requested_by_id": actor_id,
                "updated_at": stamp,
            }
        }
    )
    return token, expires_at


async def lead_for_token(token: str, *, now: datetime | None = None) -> IntakeLead | None:
    """The lead this link was made for, while it still works.

    None for a token that was never issued, has been replaced by a newer link,
    has expired, or belongs to a lead since rejected or archived.
    """
    lead = await IntakeLead.find_one({"cv_upload_token_hash": _digest(token)})
    if lead is None or lead.status in _CLOSED_STATUSES:
        return None
    expires_at = as_utc(lead.cv_upload_expires_at)
    if expires_at is None or expires_at <= (now or datetime.now(UTC)):
        return None
    return lead


def _holder(lead: IntakeLead) -> PydanticObjectId | None:
    """Whoever the lead is waiting on now, else whoever asked for the CV.

    Between the telecaller's accept and the recruiter's assignment nobody holds
    it, and the person who sent the link is the one expecting an answer.
    """
    if lead.status == IntakeLeadStatus.pending_telecaller and lead.telecaller_id:
        return lead.telecaller_id
    if lead.status == IntakeLeadStatus.pending_recruiter and lead.recruiter_id:
        return lead.recruiter_id
    return lead.cv_upload_requested_by_id


async def attach_cv(
    lead: IntakeLead,
    *,
    parsed: ParsedResume,
    raw_text: str | None,
    resume_url: str,
    resume_public_id: str | None,
    now: datetime | None = None,
) -> Candidate | None:
    """Put an uploaded CV on the lead's candidate. None if the candidate is gone.

    Merged the way a staff upload is: the file replaces any earlier one, skills
    and tags re-sync from it, and fields someone already filled in are left as
    they are. The previous file stays in Cloudinary, as it does when staff
    replace a resume.
    """
    candidate = await Candidate.find_one({"_id": lead.candidate_id, "brand_id": lead.brand_id})
    if candidate is None:
        return None
    replacing = lead.cv_uploaded_at is not None
    await candidate.set(
        build_candidate_resume_update(candidate, parsed, raw_text, resume_url, resume_public_id)
    )
    stamp = now or datetime.now(UTC)
    await IntakeLead.find_one({"_id": lead.id}).update(
        {"$set": {"cv_uploaded_at": stamp, "updated_at": stamp}}
    )
    await record_candidate_event(
        scope=TenantScope(brand_id=lead.brand_id),
        candidate_id=candidate.id,
        event_type=CandidateEventType.cv_uploaded,
        note="Sent through a CV upload link",
    )
    holder = _holder(lead)
    if holder is not None:
        await Notification(
            brand_id=lead.brand_id,
            employee_id=holder,
            intake_lead_id=lead.id,
            kind=NotificationKind.cv_uploaded,
            message=(
                f"{candidate.full_name} uploaded a new CV."
                if replacing
                else f"{candidate.full_name} uploaded their CV."
            ),
        ).insert()
    return candidate

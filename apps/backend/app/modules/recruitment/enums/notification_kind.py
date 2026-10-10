from enum import StrEnum


class NotificationKind(StrEnum):
    """What a pipeline reminder notification is about.

    Mirrors the two decision gates plus the offer-upload wait in
    controller/pipeline.py's _DECISION_GATES / dashboard/tasks.py's
    pipeline_action_reminders job.
    """

    awaiting_decision = "awaiting_decision"
    awaiting_interview_decision = "awaiting_interview_decision"
    awaiting_offer_upload = "awaiting_offer_upload"
    client_message = "client_message"
    # Intake SLA breaches. Unlike the three above, these are addressed to one
    # person (Notification.employee_id) rather than raised brand-wide.
    telecaller_sla_breach = "telecaller_sla_breach"
    recruiter_sla_breach = "recruiter_sla_breach"
    # A public-form applicant whose lead could not be opened, so no telecaller
    # will ever see them. Addressed per person, like the breaches.
    application_not_queued = "application_not_queued"
    # A candidate uploaded their CV through a link someone sent them. Addressed
    # to whoever holds the lead.
    cv_uploaded = "cv_uploaded"

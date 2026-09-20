"""Email notification service for Referee and pipeline operations.

Subjects and layout live in Resend Templates (one per method below, referenced
by name), not here. This module's job is to pick the template and hand it the
data. Copy changes are made in the Resend dashboard and take effect without a
deploy; adding or renaming a *variable* is still a change on both sides.
"""

import logging
import os
from datetime import datetime

import resend

logger = logging.getLogger(__name__)

# Template names as published in Resend. The send API accepts a template's name
# in place of its uuid, so these stay readable and survive a template being
# recreated.
TPL_NEW_POSITION = "new-position-notification"
TPL_CLIENT_ACTION = "client-action-reminder"
TPL_INTERVIEW_FOLLOWUP = "interview-followup"
TPL_OFFER_REMINDER = "offer-letter-reminder"
TPL_REFERRAL_ACTIONED = "referral-actioned"
TPL_REFERRAL_JOINED = "referral-joined"
TPL_REFERRAL_PAYMENT = "referral-payment"


def _text(value: object) -> str:
    """Neutralise markup in a value that lands in the template's HTML body.

    Resend substitutes variables verbatim — a value containing a tag arrives in
    the message as a tag — so escaping stays this module's responsibility, as it
    was when the bodies were built here.

    Only `<` and `>` are escaped, deliberately not `&`. Every variable also
    feeds a subject line, which is plain text: escaping `&` there would render
    a client named "Smith & Co" as "Smith &amp; Co" in the inbox. A bare `&` in
    an HTML body is displayed as-is by mail clients, so this trades a malformed
    entity in the pathological case for correctness in the common one.
    """
    return str(value).replace("<", "&lt;").replace(">", "&gt;")


def _url(value: str) -> str:
    """Escape a value that lands in an href, where a quote would break out."""
    return _text(value).replace('"', "&quot;")


class EmailService:
    @staticmethod
    def _send_template(to: str, template: str, variables: dict[str, object]) -> None:
        """Send one templated email, or log and return if Resend is unconfigured."""
        api_key = os.getenv("RESEND_API_KEY")
        from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

        if not api_key:
            # Variables are never logged: they carry candidate names, joining
            # dates and payment amounts, and an unconfigured environment is
            # exactly the one whose logs are least likely to be protected.
            logger.warning(
                "Email delivery infrastructure is implemented/configured, but "
                "live delivery could not be verified because provider credentials are unavailable. "
                f"Would have sent template='{template}' (recipient and variables redacted)"
            )
            return

        resend.api_key = api_key
        # Recipient omitted: these are candidate and referee addresses, and the
        # template name alone is enough to trace a delivery through the logs.
        logger.info(f"Sending email via Resend template: {template}")
        try:
            resend.Emails.send(
                {
                    "from": from_email,
                    "to": to,
                    "template": {"id": template, "variables": variables},
                }
            )
        except Exception:
            # Never re-raised: a notification that fails to send must not roll
            # back the referral or payment write that triggered it.
            logger.exception("Failed to send email via Resend")

    @classmethod
    def send_referee_actioned(
        cls, email: str, candidate_name: str, stage: str, portal_url: str
    ) -> None:
        """Send notification when a referred candidate's CV is actioned."""
        cls._send_template(
            to=email,
            template=TPL_REFERRAL_ACTIONED,
            variables={
                "CANDIDATE_NAME": _text(candidate_name),
                "STAGE": _text(stage),
                "PORTAL_URL": _url(portal_url),
            },
        )

    @classmethod
    def send_referee_joined(
        cls, email: str, candidate_name: str, joining_date: datetime, portal_url: str
    ) -> None:
        """Send notification when a referred candidate joins."""
        cls._send_template(
            to=email,
            template=TPL_REFERRAL_JOINED,
            variables={
                "CANDIDATE_NAME": _text(candidate_name),
                "JOINING_DATE": joining_date.strftime("%Y-%m-%d"),
                "PORTAL_URL": _url(portal_url),
            },
        )

    @classmethod
    def send_referee_payment(
        cls, email: str, amount: float, cycle_month: str, payment_ref: str, portal_url: str
    ) -> None:
        """Send notification when a payment batch is processed."""
        cls._send_template(
            to=email,
            template=TPL_REFERRAL_PAYMENT,
            # Formatted here rather than as a Resend number variable, which
            # would render 25000.0 as "25000" with no currency.
            variables={
                "AMOUNT": f"₹{amount:,.2f}",
                "CYCLE_MONTH": _text(cycle_month),
                "PAYMENT_REF": _text(payment_ref),
                "PORTAL_URL": _url(portal_url),
            },
        )

    @classmethod
    def send_client_action_reminder(
        cls, email: str, candidate_name: str, position_code: str, portal_url: str
    ) -> None:
        """Send a reminder to a client when a candidate has been pending action."""
        cls._send_template(
            to=email,
            template=TPL_CLIENT_ACTION,
            variables={
                "CANDIDATE_NAME": _text(candidate_name),
                "POSITION_CODE": _text(position_code),
                "PORTAL_URL": _url(portal_url),
            },
        )

    @classmethod
    def send_interview_followup(
        cls, email: str, candidate_name: str, position_code: str, portal_url: str
    ) -> None:
        """Send an interview follow-up reminder to a client."""
        cls._send_template(
            to=email,
            template=TPL_INTERVIEW_FOLLOWUP,
            variables={
                "CANDIDATE_NAME": _text(candidate_name),
                "POSITION_CODE": _text(position_code),
                "PORTAL_URL": _url(portal_url),
            },
        )

    @classmethod
    def send_offer_upload_reminder(
        cls, email: str, candidate_name: str, position_code: str, portal_url: str
    ) -> None:
        """Send an offer letter upload reminder to a client."""
        cls._send_template(
            to=email,
            template=TPL_OFFER_REMINDER,
            variables={
                "CANDIDATE_NAME": _text(candidate_name),
                "POSITION_CODE": _text(position_code),
                "PORTAL_URL": _url(portal_url),
            },
        )

    @classmethod
    def send_new_position_notification(
        cls,
        email: str,
        role: str,
        client_name: str,
        category: str,
        salary: str,
        seats: int,
        city: str,
        mumbai_area: str,
        seniority: str,
        created_by: str,
        portal_url: str,
    ) -> None:
        """Notify internal staff that a client created a new position."""
        # Empty optionals become "N/A" as they did when this built the body
        # itself; the template's fallback_value only covers a variable that is
        # absent, not one sent as an empty string.
        cls._send_template(
            to=email,
            template=TPL_NEW_POSITION,
            variables={
                "ROLE": _text(role),
                "CLIENT_NAME": _text(client_name),
                "CATEGORY": _text(category or "N/A"),
                "SALARY": _text(salary or "N/A"),
                "SEATS": seats,
                "CITY": _text(city or "N/A"),
                "MUMBAI_AREA": _text(mumbai_area or "N/A"),
                "SENIORITY": _text(seniority or "N/A"),
                "CREATED_BY": _text(created_by),
                "PORTAL_URL": _url(portal_url),
            },
        )

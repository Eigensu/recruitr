"""Email notification service for Referee operations."""

import html
import logging
import os
from datetime import datetime

import resend

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def _send_email(to: str, subject: str, body: str) -> None:
        """Internal helper to transmit email or log safely if unconfigured."""
        api_key = os.getenv("RESEND_API_KEY")
        from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

        if not api_key:
            # The body is never logged: these carry candidate names, joining
            # dates and payment amounts, and an unconfigured environment is
            # exactly the one whose logs are least likely to be protected.
            logger.warning(
                "Email delivery infrastructure is implemented/configured, but "
                "live delivery could not be verified because provider credentials are unavailable. "
                f"Would have sent to={to}, subject='{subject}' (body redacted)"
            )
            return

        resend.api_key = api_key
        logger.info(f"Sending email to {to} via Resend: {subject}")
        try:
            resend.Emails.send(
                {
                    "from": from_email,
                    "to": to,
                    "subject": subject,
                    "html": body.replace("\n", "<br>"),
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
        subject = "Your referral is now being reviewed"
        body = (
            f"Hello,\n\n"
            f"Your referred candidate, {html.escape(candidate_name)}, is currently being reviewed by our team.\n"
            f"Current Stage: {html.escape(stage)}\n\n"
            f"View their progress in your Binge Connect portal: {html.escape(portal_url)}\n\n"
            f"Best,\nThe Binge Connect Team"
        )
        cls._send_email(to=email, subject=subject, body=body)

    @classmethod
    def send_referee_joined(
        cls, email: str, candidate_name: str, joining_date: datetime, portal_url: str
    ) -> None:
        """Send notification when a referred candidate joins."""
        subject = "Your referred candidate has joined"
        date_str = joining_date.strftime("%Y-%m-%d")
        body = (
            f"Hello,\n\n"
            f"Great news! Your referred candidate, {html.escape(candidate_name)}, joined on {html.escape(date_str)}.\n"
            f"The 7 calendar-day eligibility period has started. "
            f"Your earning status is currently 'Pending' until the eligibility period is completed.\n\n"
            f"Check your portal for updates: {html.escape(portal_url)}\n\n"
            f"Best,\nThe Binge Connect Team"
        )
        cls._send_email(to=email, subject=subject, body=body)

    @classmethod
    def send_referee_payment(
        cls, email: str, amount: float, cycle_month: str, payment_ref: str, portal_url: str
    ) -> None:
        """Send notification when a payment batch is processed."""
        subject = "Your Binge Connect payment has been processed"
        body = (
            f"Hello,\n\n"
            f"Your Binge Connect payment for the {html.escape(cycle_month)} cycle has been successfully processed.\n"
            f"Amount Paid: ₹{amount:,.2f}\n"
            f"Payment Reference: {html.escape(payment_ref)}\n\n"
            f"View your payment history: {html.escape(portal_url)}\n\n"
            f"Best,\nThe Binge Connect Team"
        )
        cls._send_email(to=email, subject=subject, body=body)

    @classmethod
    def send_client_action_reminder(
        cls, email: str, candidate_name: str, position_code: str, portal_url: str
    ) -> None:
        """Send a reminder to a client when a candidate has been pending action."""
        subject = f"Action Required: Candidate {candidate_name} pending review"
        body = (
            f"Hello,\n\n"
            f"The candidate {html.escape(candidate_name)} has been waiting for your review on position {html.escape(position_code)} for over 2 days.\n\n"
            f"Please log in to your portal to review their profile and update their status:\n"
            f"{html.escape(portal_url)}\n\n"
            f"Best,\nThe Recruitment Team"
        )
        cls._send_email(to=email, subject=subject, body=body)

    @classmethod
    def send_interview_followup(
        cls, email: str, candidate_name: str, position_code: str, portal_url: str
    ) -> None:
        """Send an interview follow-up reminder to a client."""
        subject = f"Action Required: Interview feedback for {candidate_name}"
        body = (
            f"Hello,\n\n"
            f"An interview was scheduled for {html.escape(candidate_name)} on position {html.escape(position_code)} over 2 days ago.\n\n"
            f"Please log in to your portal to submit your feedback and update their status (Selected / Rejected):\n"
            f"{html.escape(portal_url)}\n\n"
            f"Best,\nThe Recruitment Team"
        )
        cls._send_email(to=email, subject=subject, body=body)

    @classmethod
    def send_offer_upload_reminder(
        cls, email: str, candidate_name: str, position_code: str, portal_url: str
    ) -> None:
        """Send an offer letter upload reminder to a client."""
        subject = f"Action Required: Offer letter pending for {candidate_name}"
        body = (
            f"Hello,\n\n"
            f"The candidate {html.escape(candidate_name)} was marked as Selected for position {html.escape(position_code)} over 2 days ago, but an offer letter has not been uploaded yet.\n\n"
            f"Please log in to your portal to upload the offer letter and proceed with their onboarding:\n"
            f"{html.escape(portal_url)}\n\n"
            f"Best,\nThe Recruitment Team"
        )
        cls._send_email(to=email, subject=subject, body=body)

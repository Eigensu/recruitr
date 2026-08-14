"""Email notification service for Referee operations."""

import html
import logging
import os
from datetime import datetime

import resend

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def _send_email(to: str, subject: str, body: str, secure_log: bool = False) -> None:
        """Internal helper to transmit email or log safely if unconfigured."""
        api_key = os.getenv("RESEND_API_KEY")
        from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

        if not api_key:
            log_body = "*** REDACTED ***" if secure_log else body
            logger.warning(
                "Email delivery infrastructure is implemented/configured, but "
                "live delivery could not be verified because provider credentials are unavailable. "
                f"Would have sent to={to}, subject='{subject}', body='{log_body}'"
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
        except Exception as e:
            logger.error(f"Failed to send email via Resend: {e}")

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

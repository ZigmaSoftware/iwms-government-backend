import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


def send_otp_email(recipient_email: str, otp_code: str, username: str = "") -> bool:
    """
    Send OTP to the customer's email via SMTP.
    Returns True on success, False on failure.
    """
    expiry = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
    subject = "Your Password Reset OTP – IWMS"
    body = (
        f"Hi {username or 'User'},\n\n"
        f"Your one-time password (OTP) for resetting your IWMS account password is:\n\n"
        f"    {otp_code}\n\n"
        f"This OTP is valid for {expiry} minutes.\n"
        f"Do not share this code with anyone.\n\n"
        f"If you did not request this, please ignore this email.\n\n"
        f"— IWMS Support"
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        logger.info("OTP email sent to %s", recipient_email)
        return True
    except Exception as exc:
        logger.error("Failed to send OTP email to %s: %s", recipient_email, exc)
        return False


def send_grievance_confirmation_email(recipient_email: str, ticket_no: str, person_name: str = "") -> bool:
    """
    Send a public-grievance confirmation with the ticket number and follow-up
    details to the citizen's email. Returns True on success, False on failure.
    """
    subject = f"Grievance Received - Ticket {ticket_no}"
    body = (
        f"Hi {person_name or 'there'},\n\n"
        f"Thank you for reporting your grievance. It has been registered successfully.\n\n"
        f"    Ticket No: {ticket_no}\n\n"
        f"Our team will review it and take the necessary action. You can use this "
        f"ticket number to check the status of your complaint anytime on the Public "
        f"Grievance portal.\n\n"
        f"- IWMS Support"
    )
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        logger.info("Grievance confirmation email sent to %s for ticket %s", recipient_email, ticket_no)
        return True
    except Exception as exc:
        logger.error("Failed to send grievance confirmation email to %s: %s", recipient_email, exc)
        return False

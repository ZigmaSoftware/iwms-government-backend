from django.conf import settings

from app.tasks import enqueue
from app.tasks.notification_tasks import send_email_task


def send_otp_email(recipient_email: str, otp_code: str, username: str = "") -> None:
    """
    Queue the password-reset OTP email. Sent via SMTP by the Celery worker,
    which retries transient SMTP failures.
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
    enqueue(send_email_task, subject, body, [recipient_email], "password reset OTP")


def send_grievance_confirmation_email(recipient_email: str, ticket_no: str, person_name: str = "") -> None:
    """
    Queue a public-grievance confirmation with the ticket number and follow-up
    details to the citizen's email (sent by the Celery worker).
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
    enqueue(send_email_task, subject, body, [recipient_email], f"grievance ticket {ticket_no}")

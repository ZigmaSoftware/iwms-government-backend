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

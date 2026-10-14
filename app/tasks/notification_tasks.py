"""Outbound notifications (FCM push, email), sent off the request path.

Queue these through the service helpers (push_notification_service,
email_utils) rather than directly; they decide whether anything needs sending.
"""
import logging
from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

PUSH_MAX_RETRIES = 3


@shared_task(bind=True, name="iwms.send_push", max_retries=PUSH_MAX_RETRIES)
def send_push_task(self, token, title, body, data, recipient):
    from app.services.push_notification_service import deliver_push, is_transient_push_error

    try:
        deliver_push(token, title, body, data)
    except Exception as exc:
        if is_transient_push_error(exc) and self.request.retries < PUSH_MAX_RETRIES:
            raise self.retry(exc=exc, countdown=30 * 2 ** self.request.retries)
        logger.exception("[push] Failed to send push to %s", recipient)


@shared_task(
    name="iwms.send_email",
    autoretry_for=(SMTPException, OSError),
    retry_backoff=30,
    retry_backoff_max=600,
    max_retries=3,
)
def send_email_task(subject, body, recipient_list, log_label=""):
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        fail_silently=False,
    )
    logger.info("Email sent to %s%s", ", ".join(recipient_list), f" ({log_label})" if log_label else "")

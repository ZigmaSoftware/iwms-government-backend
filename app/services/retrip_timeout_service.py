"""Deadline processing for supervisor Re-Trip decisions.

A driver's Re-Trip request is short-lived: the supervisor gets a reminder,
then an urgent escalation, and if nobody decides within the window the
request expires and the trip simply stays open (the driver may continue or
raise a new request).

Run every minute by the Celery beat entry `retrip-timeouts`
(`iwms.process_retrip_timeouts`, app/tasks/scheduler_tasks.py) and on demand
by `manage.py process_retrip_timeouts`. Every transition is stamped on the
row under a row lock, so overlapping runs never notify twice.

Windows (minutes, from the request's creation) come from the environment:
    RETRIP_EXPIRY_MINUTES      default 30
    RETRIP_REMINDER_MINUTES    default 10
    RETRIP_ESCALATION_MINUTES  default 20
"""

import os
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from app.models.core_modules.daily_operations.trip_retrip_request import (
    TripRetripRequest,
)
from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.services.staff_notification_service import notify_staff


def _minutes(name, default):
    try:
        return max(1, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        return default


def timeout_minutes():
    return _minutes("RETRIP_EXPIRY_MINUTES", 30)


def reminder_minutes():
    return min(_minutes("RETRIP_REMINDER_MINUTES", 10), timeout_minutes())


def escalation_minutes():
    return min(_minutes("RETRIP_ESCALATION_MINUTES", 20), timeout_minutes())


def deadline_for(retrip):
    if retrip.expires_at:
        return retrip.expires_at
    return retrip.created_at + timedelta(minutes=timeout_minutes())


def _supervisors_for(retrip):
    assignment = retrip.assignment
    plan = assignment.trip_plan if assignment else None
    supervisor = getattr(plan, "supervisor", None) if plan else None
    return [supervisor] if supervisor is not None else []


def _crew_for(retrip):
    assignment = retrip.assignment
    if assignment is None:
        return []
    template = assignment.effective_template
    if template is None:
        return []
    return [
        staff
        for staff in (getattr(template, "driver", None), getattr(template, "operator", None))
        if staff is not None
    ]


def _notify(recipients, notification_type, title, message, retrip, event):
    for recipient in recipients:
        notify_staff(
            recipient,
            notification_type,
            title,
            message,
            data={
                "event": event,
                "retrip_request_id": retrip.unique_id,
                "assignment_id": retrip.assignment_id,
                "expires_at": deadline_for(retrip).isoformat(),
            },
        )


def _expire_locked(retrip, now):
    if not retrip.is_pending or now < deadline_for(retrip):
        return False

    retrip.status = TripRetripRequest.STATUS_EXPIRED
    retrip.expires_at = deadline_for(retrip)
    retrip.reviewed_at = now
    retrip.review_remarks = (
        f"Expired automatically after {timeout_minutes()} minutes without "
        "a supervisor decision."
    )
    retrip.save(
        update_fields=[
            "status",
            "expires_at",
            "reviewed_at",
            "review_remarks",
            "updated_at",
        ]
    )

    _notify(
        _supervisors_for(retrip),
        StaffNotification.TYPE_RETRIP_EXPIRED,
        "Re-Trip request expired",
        f"The decision window for {retrip.assignment_id} expired. The trip remains open.",
        retrip,
        "retrip_expired",
    )
    _notify(
        _crew_for(retrip),
        StaffNotification.TYPE_RETRIP_EXPIRED,
        "Re-Trip request expired",
        f"Your request for {retrip.assignment_id} expired without a decision. "
        "You can continue the trip or submit a new request.",
        retrip,
        "retrip_expired",
    )
    return True


@transaction.atomic
def expire_retrip_if_due(retrip, now=None):
    """Expire one request under a row lock. Returns True only on transition."""
    now = now or timezone.now()
    locked = TripRetripRequest.objects.select_for_update().get(pk=retrip.pk)
    return _expire_locked(locked, now)


def process_retrip_timeouts(now=None):
    """Send due reminders/escalations and expire stale requests exactly once."""
    now = now or timezone.now()
    result = {"reminded": 0, "escalated": 0, "expired": 0}
    pending_ids = list(
        TripRetripRequest.objects.filter(
            status=TripRetripRequest.STATUS_PENDING,
            is_deleted=False,
        ).values_list("pk", flat=True)
    )

    for request_id in pending_ids:
        with transaction.atomic():
            retrip = TripRetripRequest.objects.select_for_update().filter(
                pk=request_id,
                status=TripRetripRequest.STATUS_PENDING,
                is_deleted=False,
            ).first()
            if retrip is None:
                continue

            deadline = deadline_for(retrip)
            if retrip.expires_at is None:
                retrip.expires_at = deadline
                retrip.save(update_fields=["expires_at", "updated_at"])

            if _expire_locked(retrip, now):
                result["expired"] += 1
                continue

            age = now - retrip.created_at
            if age >= timedelta(minutes=escalation_minutes()) and retrip.escalated_at is None:
                retrip.escalated_at = now
                if retrip.reminder_sent_at is None:
                    retrip.reminder_sent_at = now
                retrip.save(
                    update_fields=["escalated_at", "reminder_sent_at", "updated_at"]
                )
                remaining = max(0, int((deadline - now).total_seconds() // 60))
                _notify(
                    _supervisors_for(retrip),
                    StaffNotification.TYPE_RETRIP_ESCALATED,
                    "Urgent Re-Trip decision",
                    f"{retrip.assignment_id} expires in about {remaining} minute(s).",
                    retrip,
                    "retrip_escalated",
                )
                result["escalated"] += 1
            elif age >= timedelta(minutes=reminder_minutes()) and retrip.reminder_sent_at is None:
                retrip.reminder_sent_at = now
                retrip.save(update_fields=["reminder_sent_at", "updated_at"])
                _notify(
                    _supervisors_for(retrip),
                    StaffNotification.TYPE_RETRIP_REMINDER,
                    "Re-Trip decision reminder",
                    f"{retrip.assignment_id} is still waiting for your decision.",
                    retrip,
                    "retrip_reminder",
                )
                result["reminded"] += 1

    return result

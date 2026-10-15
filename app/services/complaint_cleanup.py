"""Citizen cleanup reports ("Verify Cleanup" on the public complaint map).

A citizen sends a photo of the cleaned spot; it waits as a PENDING
`ComplaintCleanupReport` for the officer the ticket currently sits with.

- approve → the ticket is CLOSED (escalation stops, the citizen is told)
- reject  → the ticket stays open on its escalation clock, and citizens can
  report again

Only the current handler (the staff member the ticket is with now) may
review; admin logins that aren't staff records may too, as an override.
Every review needs remarks — they go on the ticket's history.
"""
from django.db import transaction
from django.utils import timezone

from app.models.core_modules.complaint_management.cleanup_report import ComplaintCleanupReport

CLEANUP_PROOF = "cleanup_proof"  # ComplaintAttachment.file_type of the photo


class CleanupError(ValueError):
    pass


def pending_report(ticket):
    return ComplaintCleanupReport.objects.filter(
        ticket_id=ticket.unique_id, status=ComplaintCleanupReport.STATUS_PENDING, is_deleted=False,
    ).order_by("-created").first()


def can_review(ticket, user):
    """Staff logins: only the staff member handling the ticket now. Other
    (admin) logins: allowed."""
    if getattr(user, "is_superuser", False):
        return True
    staff_uid = getattr(user, "staff_unique_id", None)
    if staff_uid is None:
        return bool(getattr(user, "is_authenticated", False))
    handler = ticket.responsible_staff
    return bool(handler and handler.staff_unique_id == staff_uid)


@transaction.atomic
def submit(ticket, photo, note=""):
    """Store the citizen's photo + note as a PENDING report and notify the
    handling officer."""
    from app.models.core_modules.complaint_management.comment import ComplaintComment
    from app.models.core_modules.complaint_management.notification import ComplaintNotification
    from app.models.core_modules.complaint_management.ticket_attachment import ComplaintAttachment
    from app.services import notification_service

    if pending_report(ticket):
        raise CleanupError("A cleanup photo for this complaint is already waiting for the officer's check.")

    attachment = ComplaintAttachment.objects.create(
        ticket_id=ticket.unique_id,
        file=photo,
        file_name=getattr(photo, "name", None),
        file_type=CLEANUP_PROOF,
        mime_type=getattr(photo, "content_type", None),
        file_size=getattr(photo, "size", None),
    )
    report = ComplaintCleanupReport.objects.create(
        ticket_id=ticket.unique_id, attachment_id=attachment.unique_id, note=note or None,
    )
    ComplaintComment.objects.create(
        ticket_id=ticket.unique_id,
        comment_text="Citizen reported this spot as cleaned (photo sent from the public map) — waiting for verification."
        + (f" Note: {note}" if note else ""),
        is_internal=True,
    )
    staff = ticket.responsible_staff
    if staff:
        notification_service.notify(
            ticket,
            ComplaintNotification.EVENT_CLEANUP_REPORTED,
            f"A citizen says ticket {ticket.ticket_no} has been cleaned up. "
            "Check the photo and approve to close it, or reject it.",
            staff=staff,
        )
    return report


def _require_remarks(remarks):
    remarks = (remarks or "").strip()
    if not remarks:
        raise CleanupError("Remarks are required to approve or reject a cleanup.")
    return remarks


def _reviewer_fields(user):
    staff_uid = getattr(user, "staff_unique_id", None)
    return {
        "reviewed_by_staff_id": staff_uid,
        "reviewed_by_user_id": None if staff_uid else getattr(user, "unique_id", None),
        "reviewed_at": timezone.now(),
    }


def _reviewer_name(user):
    return getattr(user, "employee_name", None) or getattr(user, "username", None) or "the officer"


@transaction.atomic
def approve(ticket, report, user, remarks):
    """Accept the cleanup and close the ticket."""
    from app.models.core_modules.complaint_management.status_history import ComplaintStatusHistory
    from app.models.core_modules.complaint_management.status_master import ComplaintStatus
    from app.models.core_modules.complaint_management.ticket import ComplaintTicket
    from app.services.complaint_escalation import CLOSED_STATUS_CODES
    from app.services.push_notification_service import send_push_to_customer

    remarks = _require_remarks(remarks)
    report = ComplaintCleanupReport.objects.select_for_update().get(pk=report.pk)
    if report.status != ComplaintCleanupReport.STATUS_PENDING:
        raise CleanupError("This cleanup report has already been reviewed.")
    closed = ComplaintStatus.objects.filter(status_code="CLOSED", is_deleted=False).first()
    if not closed:
        raise CleanupError("CLOSED status is not configured.")

    ticket = ComplaintTicket.objects.select_for_update().get(pk=ticket.pk)
    old_status = ticket.status
    if old_status and old_status.status_code in CLOSED_STATUS_CODES:
        raise CleanupError("This complaint is already closed.")

    now = timezone.now()
    ticket.status_id = closed.unique_id
    ticket.resolved_at = ticket.resolved_at or now
    ticket.closed_at = ticket.closed_at or now
    ticket.next_escalation_due_at = None
    ticket.save(update_fields=["status_id", "resolved_at", "closed_at", "next_escalation_due_at"])

    for field, value in {**_reviewer_fields(user), "status": ComplaintCleanupReport.STATUS_APPROVED,
                         "review_remarks": remarks}.items():
        setattr(report, field, value)
    report.save()

    actor_user_id = None if getattr(user, "staff_unique_id", None) else getattr(user, "unique_id", None)
    ComplaintStatusHistory.objects.create(
        ticket_id=ticket.unique_id,
        from_status_id=getattr(old_status, "unique_id", None),
        to_status_id=closed.unique_id,
        changed_by_user_id=actor_user_id,
        remarks=f"Cleanup verified by {_reviewer_name(user)}: {remarks}",
        visible_to_citizen=True,
    )
    send_push_to_customer(
        ticket.customer,
        "Grievance update",
        f"Your ticket {ticket.ticket_no} has been verified as cleaned up and closed.",
        data={"event": "ticket_closed", "ticket_id": str(ticket.unique_id)},
    )
    return ticket


@transaction.atomic
def reject(ticket, report, user, remarks):
    """Not clean yet: the ticket stays open where it is."""
    from app.models.core_modules.complaint_management.comment import ComplaintComment

    remarks = _require_remarks(remarks)
    report = ComplaintCleanupReport.objects.select_for_update().get(pk=report.pk)
    if report.status != ComplaintCleanupReport.STATUS_PENDING:
        raise CleanupError("This cleanup report has already been reviewed.")
    for field, value in {**_reviewer_fields(user), "status": ComplaintCleanupReport.STATUS_REJECTED,
                         "review_remarks": remarks}.items():
        setattr(report, field, value)
    report.save()
    ComplaintComment.objects.create(
        ticket_id=ticket.unique_id,
        comment_text=f"Citizen cleanup photo rejected by {_reviewer_name(user)}: {remarks}",
        is_internal=True,
    )
    return report

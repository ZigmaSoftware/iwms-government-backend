"""Creates in-app ComplaintNotification rows for grievance lifecycle events.

Single choke point for assign / escalate / resolve / reopen so every code
path (manual API action or the automated SLA-breach sweep) notifies the
same way. Recipients log in either as a StaffcreationOfficeDetails record
or an AUTH_USER_MODEL account (see app.authentication.jwt); pass whichever
one applies.
"""
from app.models.core_modules.complaint_management.notification import ComplaintNotification

EVENT_TITLES = {
    ComplaintNotification.EVENT_ASSIGNED: "New grievance assigned to you",
    ComplaintNotification.EVENT_ESCALATED: "Grievance escalated",
    ComplaintNotification.EVENT_ESCALATED_TO: "Grievance escalated to you",
    ComplaintNotification.EVENT_RESOLVED: "Grievance resolved",
    ComplaintNotification.EVENT_REOPENED: "Grievance reopened",
}


def notify(ticket, event_type, message, *, staff=None, user=None):
    """Create one notification for a single staff or user recipient."""
    if not staff and not user:
        return None
    return ComplaintNotification.objects.create(
        ticket=ticket,
        recipient_staff=staff,
        recipient_user=user,
        event_type=event_type,
        title=EVENT_TITLES.get(event_type, "Grievance update"),
        message=message,
    )


def notify_many(ticket, event_type, message, *, staff_list=(), user_list=()):
    """Create notifications for several recipients, skipping None/duplicates."""
    created = []
    seen_staff, seen_user = set(), set()
    for staff in staff_list:
        if staff and staff.pk not in seen_staff:
            seen_staff.add(staff.pk)
            created.append(notify(ticket, event_type, message, staff=staff))
    for user in user_list:
        if user and user.pk not in seen_user:
            seen_user.add(user.pk)
            created.append(notify(ticket, event_type, message, user=user))
    return created

"""Single choke point for a staff member's in-app + push notification.

Every operational event that should alert a driver/operator/supervisor (vehicle
replacement approval/rejection, team reassignment, substitution) should call
`notify_staff` instead of `send_push_to_staff` directly, so the alert is
always visible in-app (a `StaffNotification` row) even if the push never
reaches the device (no token, app killed, Firebase not configured yet).
"""
from app.models.core_modules.notifications.staff_notification import StaffNotification
from app.services.push_notification_service import send_push_to_staff


def notify_staff(staff, notification_type, title, body, data=None):
    """Create a StaffNotification row for `staff` and send the matching push.

    Returns the created StaffNotification, or None if `staff` is None.
    """
    if staff is None:
        return None

    notification = StaffNotification.objects.create(
        recipient_staff=staff,
        notification_type=notification_type,
        title=title,
        message=body,
        data=data or {},
    )

    send_push_to_staff(
        staff,
        title=title,
        body=body,
        data={**(data or {}), "type": notification_type},
    )

    return notification

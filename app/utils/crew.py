"""Shared "who's on this vehicle today" crew-payload builder.

Used by both the mobile driver serializer (operator_mobile/trip_today_serializer.py,
"Your crew" on the home page) and the desktop/supervisor assignment serializer
(core_modules/daily_operations/daily_trip_assignment_serializer.py, the Teams /
Trips "spectate" views), so the two stay in lockstep instead of drifting.
"""


class CrewPresenceCache:
    """Caches DailyAttendanceReg lookups per trip_date across many crew_member()
    calls in a single serializer pass (e.g. one per row in a list response)."""

    def __init__(self):
        self._cache = {}

    def present_staff_ids(self, trip_date):
        if trip_date in self._cache:
            return self._cache[trip_date]

        from app.models.core_modules.attendance import DailyAttendanceReg

        present_ids = set(
            DailyAttendanceReg.objects.filter(
                recognition_date=trip_date,
            ).values_list("staff_id", flat=True)
        )
        self._cache[trip_date] = present_ids
        return present_ids


def crew_member_payload(staff, role, trip_date, *, request=None, presence_cache=None):
    """A single crew member's payload: identity, photo, and today's attendance."""
    if staff is None:
        return None

    # Prefer the face registered for attendance; fall back to an admin-uploaded
    # staff photo — same precedence as the header avatars.
    photo = getattr(staff, "attendance_reg_image", None) or getattr(staff, "photo", None)
    photo_url = None
    try:
        if photo:
            photo_url = request.build_absolute_uri(photo.url) if request is not None else photo.url
    except (ValueError, AttributeError):
        photo_url = None

    is_present = False
    if presence_cache is not None:
        is_present = getattr(staff, "staff_unique_id", None) in presence_cache.present_staff_ids(
            trip_date
        )

    return {
        "unique_id": staff.staff_unique_id,
        "name": staff.employee_name,
        "emp_id": staff.emp_id,
        "role": role,
        "phone": getattr(staff, "contact_mobile", None),
        "photo_url": photo_url,
        "is_present": is_present,
        "attendance_status": "Present" if is_present else "Absent",
    }


def crew_payload(template, alt, trip_date, *, request=None, presence_cache=None):
    """Full crew payload (driver + operator + extras) for an assignment, given
    its regular `staff_template` and (possibly None) active `alt_staff_template`.
    An active alternative overrides the regular crew for its date range — same
    source of truth as `get_effective_staff` on the desktop serializer."""
    from app.models.user_creations.staffcreation import Staffcreation

    source = alt if alt is not None else template
    if source is None:
        return None

    if presence_cache is None:
        presence_cache = CrewPresenceCache()

    extra_ids = list(getattr(source, "extra_operator_id", None) or [])
    extras = []
    if extra_ids:
        extras = list(
            Staffcreation.objects.filter(staff_unique_id__in=extra_ids, is_deleted=False)
        )

    def member(staff, role):
        return crew_member_payload(
            staff, role, trip_date, request=request, presence_cache=presence_cache
        )

    return {
        "driver": member(getattr(source, "driver_id", None), "Driver"),
        "operator": member(getattr(source, "operator_id", None), "Operator"),
        "extra_operators": [m for m in (member(s, "Operator") for s in extras) if m],
        "is_alt_active": alt is not None,
        "template_code": getattr(template, "display_code", None),
        "alt_template_code": getattr(alt, "display_code", None),
    }

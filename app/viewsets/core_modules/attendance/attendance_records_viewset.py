import os

from django.conf import settings
from django.db.models import Count, Max, Min, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.core_modules.attendance import DailyAttendanceReg
from app.models.superadmin.user_management.staffcreation import Staffcreation
from app.utils.hierarchy import filter_staff_queryset_by_requester_scope


def _build_image_url(request, captured_image_path):
    if not captured_image_path or isinstance(captured_image_path, (bytes, bytearray, memoryview)):
        return None
    filename = os.path.basename(str(captured_image_path))
    media_url = f"{settings.MEDIA_URL}captured_images/{filename}"
    return request.build_absolute_uri(media_url) if request else media_url


class AttendanceRecordsViewSet(ViewSet):
    """Admin attendance list backed by the local staff attendance module.

    Groups raw device punches into one row per (staff, day) — first-in /
    last-out / punch-count — server-side, then paginates the GROUPED rows.
    Grouping must happen before pagination: paginating raw punches directly
    would silently split a single person's day across two pages, breaking
    the first-in/last-out computation at the page boundary.
    """

    permission_classes = [IsAuthenticated]
    permission_resource = "DailyAttendanceReg"
    swagger_tags = ["Attendance"]

    @staticmethod
    def _date_range(request):
        today = timezone.localdate()
        from_date = parse_date(request.query_params.get("from_date", "")) or today
        to_date = parse_date(request.query_params.get("to_date", "")) or today
        if from_date > to_date:
            raise ValidationError({"to_date": "to_date must be on or after from_date"})
        return from_date, to_date

    @staticmethod
    def _pagination(request, default_limit=20, max_limit=200):
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            limit = int(request.query_params.get("limit", default_limit))
        except (TypeError, ValueError):
            limit = default_limit
        limit = max(1, min(limit, max_limit))
        offset = (page - 1) * limit
        return offset, limit

    def list(self, request):
        from_date, to_date = self._date_range(request)
        offset, limit = self._pagination(request)

        visible_staff = filter_staff_queryset_by_requester_scope(
            Staffcreation.objects.filter(is_deleted=False), request.user
        )
        base_qs = DailyAttendanceReg.objects.filter(
            staff__in=visible_staff,
            recognition_date__range=(from_date, to_date),
        )

        grouped = (
            base_qs
            .values("emp_id", "name", "recognition_date")
            .annotate(
                # Prefer the explicitly-tagged IN/OUT punch; fall back to the
                # chronologically first/last punch of the day when a device
                # never tagged one (mirrors the old client-side heuristic).
                first_in_marked=Min("recognition_time", filter=Q(punch_type="IN")),
                first_punch_time=Min("recognition_time"),
                last_out_marked=Max("recognition_time", filter=Q(punch_type="OUT")),
                last_punch_time=Max("recognition_time"),
                punch_count=Count("unique_id"),
            )
            .order_by("-recognition_date", "emp_id")
        )

        total = grouped.count()
        page_rows = list(grouped[offset:offset + limit])

        # One follow-up query for the current page's first-in punches only,
        # to attach lat/long/captured_image (not aggregatable — they belong
        # to a specific punch row, not the group).
        detail_q = Q()
        for row in page_rows:
            first_in_time = row["first_in_marked"] or row["first_punch_time"]
            detail_q |= Q(
                emp_id=row["emp_id"],
                recognition_date=row["recognition_date"],
                recognition_time=first_in_time,
            )
        details_by_key = {}
        if page_rows:
            for detail in base_qs.filter(detail_q).values(
                "emp_id", "recognition_date", "recognition_time", "latitude", "longitude", "captured_image_path"
            ):
                key = (detail["emp_id"], detail["recognition_date"], detail["recognition_time"])
                details_by_key.setdefault(key, detail)

        results = []
        for row in page_rows:
            first_in_time = row["first_in_marked"] or row["first_punch_time"]
            last_out_time = row["last_out_marked"] or row["last_punch_time"]
            detail = details_by_key.get((row["emp_id"], row["recognition_date"], first_in_time), {})
            results.append({
                "key": f"{row['emp_id']}__{row['recognition_date']}",
                "emp_id": row["emp_id"],
                "name": row["name"],
                "recognition_date": str(row["recognition_date"]),
                "first_in_time": str(first_in_time) if first_in_time else None,
                "last_out_time": str(last_out_time) if last_out_time else None,
                "punch_count": row["punch_count"],
                "latitude": detail.get("latitude"),
                "longitude": detail.get("longitude"),
                "captured_image": _build_image_url(request, detail.get("captured_image_path")),
            })

        return Response({"count": total, "records": results})

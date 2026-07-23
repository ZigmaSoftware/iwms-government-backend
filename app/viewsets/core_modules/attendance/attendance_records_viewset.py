from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.core_modules.attendance import DailyAttendanceReg
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.core_modules.attendance import DailyAttendanceRegSerializer
from app.utils.hierarchy import filter_staff_queryset_by_requester_scope


class AttendanceRecordsViewSet(ViewSet):
    """Admin attendance list backed by the local staff attendance module."""

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

    def list(self, request):
        from_date, to_date = self._date_range(request)
        visible_staff = filter_staff_queryset_by_requester_scope(
            Staffcreation.objects.filter(is_deleted=False), request.user
        ).select_related(
            "designation_id",
            "department_id",
            "staffusertype_id",
            "personal_details",
        )
        records = (
            DailyAttendanceReg.objects.filter(
                staff__in=visible_staff,
                recognition_date__range=(from_date, to_date),
            )
            .select_related("staff")
            .order_by("-records")
        )
        present_staff_ids = set(records.values_list("staff_id", flat=True).distinct())
        staff_items = list(visible_staff)
        present_staff = [
            self._serialize_staff_member(staff, "present")
            for staff in staff_items
            if staff.staff_unique_id in present_staff_ids
        ]
        absent_staff = [
            self._serialize_staff_member(staff, "absent")
            for staff in staff_items
            if staff.staff_unique_id not in present_staff_ids
        ]
        serializer = DailyAttendanceRegSerializer(
            records, many=True, context={"request": request}
        )
        return Response(
            {
                "count": records.count(),
                "records": serializer.data,
                "staff_summary": {
                    "present_count": len(present_staff),
                    "absent_count": len(absent_staff),
                    "leave_count": 0,
                    "present_staff": present_staff,
                    "absent_staff": absent_staff,
                    "leave_staff": [],
                },
            }
        )

    @staticmethod
    def _serialize_staff_member(staff, attendance_status):
        designation = (
            getattr(getattr(staff, "designation_id", None), "designation_name", None)
            or getattr(staff, "designation", None)
            or ""
        )
        department = (
            getattr(getattr(staff, "department_id", None), "department_name", None)
            or getattr(staff, "department", None)
            or ""
        )
        role = getattr(getattr(staff, "staffusertype_id", None), "name", None) or ""
        mobile = getattr(getattr(staff, "personal_details", None), "contact_mobile", None) or ""
        return {
            "unique_id": getattr(staff, "staff_unique_id", ""),
            "staff_unique_id": getattr(staff, "staff_unique_id", ""),
            "emp_id": getattr(staff, "emp_id", ""),
            "employee_name": getattr(staff, "employee_name", ""),
            "designation": designation,
            "designation_name": designation,
            "department": department,
            "department_name": department,
            "staffusertype_name": role,
            "contact_mobile": mobile,
            "attendance_status": attendance_status,
        }

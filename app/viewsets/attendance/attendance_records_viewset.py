from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.attendance import DailyAttendanceReg
from app.models.user_creations.staffcreation import Staffcreation
from app.serializers.attendance import DailyAttendanceRegSerializer
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
        )
        records = (
            DailyAttendanceReg.objects.filter(
                staff__in=visible_staff,
                recognition_date__range=(from_date, to_date),
            )
            .select_related("staff")
            .order_by("-records")
        )
        serializer = DailyAttendanceRegSerializer(
            records, many=True, context={"request": request}
        )
        return Response({"count": records.count(), "records": serializer.data})

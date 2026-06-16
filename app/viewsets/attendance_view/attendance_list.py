from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.conf import settings
from django.utils import timezone

from app.models.user_creations.attendance import Recognized


class AttendanceListViewSet(ViewSet):

    def _to_media_url(self, path):
        if not path:
            return None

        path = str(path).replace("\\", "/")

        if path.startswith("http"):
            return path

        media_root = settings.MEDIA_ROOT.replace("\\", "/")
        if media_root in path:
            path = path.split(media_root)[-1]

        return f"{settings.MEDIA_URL}{path.lstrip('/')}"

    def list(self, request):
        emp_id = request.query_params.get("emp_id")
        month = request.query_params.get("month")
        year = request.query_params.get("year")

        if not emp_id or not month or not year:
            return Response(
                {"status": "error", "message": "emp_id, month, year required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        records = Recognized.objects.filter(
            staff__staff_unique_id=emp_id,
            recognition_date__month=int(month),
            recognition_date__year=int(year),
        ).order_by("recognition_date", "recognition_time")

        dates = records.values_list(
            "recognition_date", flat=True
        ).distinct().order_by("-recognition_date")

        result = []

        for d in dates:
            day_records = records.filter(recognition_date=d)

            check_in = (
                day_records.filter(punch_type="IN").order_by("records").first()
                or day_records.first()
            )
            check_out = day_records.filter(punch_type="OUT").order_by("-records").first()
            has_in = day_records.filter(punch_type="IN").exists()
            has_out = day_records.filter(punch_type="OUT").exists()
            day_status = "Present" if (has_in and has_out) else (
                "Pending OUT" if has_in else "Absent"
            )

            result.append({
                "date": d.strftime("%d/%B/%Y"),

                "in_time": check_in.recognition_time.strftime("%H:%M") if check_in else None,
                "out_time": (
                    check_out.recognition_time.strftime("%H:%M")
                    if check_out and (not check_in or check_out.pk != check_in.pk)
                    else None
                ),

                "in_latitude": check_in.latitude if check_in else None,
                "in_longitude": check_in.longitude if check_in else None,
                "out_latitude": check_out.latitude if check_out else None,
                "out_longitude": check_out.longitude if check_out else None,

                "in_image_path": self._to_media_url(
                    check_in.captured_image_path if check_in else None
                ),
                "out_image_path": self._to_media_url(
                    check_out.captured_image_path
                    if check_out and (not check_in or check_out.pk != check_in.pk)
                    else None
                ),
                "last_punch_type": day_records.last().punch_type if day_records.exists() else None,
                "day_status": day_status,
            })

        return Response(
            {
                "status": "success",
                "count": len(result),
                "records": result
            },
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        emp_id = request.query_params.get("emp_id")
        if not emp_id:
            return Response(
                {"status": "error", "message": "emp_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()
        records = (
            Recognized.objects
            .filter(staff__staff_unique_id=emp_id, recognition_date=today)
            .order_by("records")
        )

        has_in = records.filter(punch_type="IN").exists()
        has_out = records.filter(punch_type="OUT").exists()

        check_in = (
            records.filter(punch_type="IN").order_by("records").first()
            or records.first()
        )
        check_out = records.filter(punch_type="OUT").order_by("-records").first()
        last = records.last()
        last_type = last.punch_type if last else None
        next_punch = "OUT" if last_type == "IN" else "IN"

        return Response(
            {
                "status": "success",
                "check_in_time": check_in.recognition_time.strftime("%H:%M") if check_in else None,
                "check_out_time": check_out.recognition_time.strftime("%H:%M") if check_out else None,
                "checked_in": has_in,
                "checked_out": has_out,
                "last_punch_type": last_type,
                "next_punch": next_punch,
                "total_punches": records.count(),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        emp_id = request.query_params.get("emp_id")
        month = request.query_params.get("month")
        year = request.query_params.get("year")

        if not emp_id or not month or not year:
            return Response(
                {"status": "error", "message": "emp_id, month, year required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        records = Recognized.objects.filter(
            staff__staff_unique_id=emp_id,
            recognition_date__month=int(month),
            recognition_date__year=int(year),
        )
        dates = (
            records.values_list("recognition_date", flat=True)
            .distinct()
        )

        present_days = 0
        for d in dates:
            day_records = records.filter(recognition_date=d)
            has_in = day_records.filter(punch_type="IN").exists()
            has_out = day_records.filter(punch_type="OUT").exists()
            if has_in and has_out:
                present_days += 1

        return Response(
            {
                "status": "success",
                "present_days": present_days,
                "leave_days": 0,
                "permission_days": 0,
                "total_punches": records.count(),
            },
            status=status.HTTP_200_OK,
        )

import os
import requests

from rest_framework.viewsets import ModelViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.utils import timezone

from app.models.masters.transport_masters.trip_attendance import TripAttendance
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.serializers.masters.transport_masters.trip_attendance_serializer import (
    TripAttendanceSerializer
)
from app.utils.scoped_viewset import FlatGeoScopedViewSetMixin


class TripAttendanceViewSet(FlatGeoScopedViewSetMixin, ModelViewSet):
    """
    Mobile-triggered periodic attendance capture.
    Invoked every 45 minutes per staff during a trip.

    Corporation scoping (params + requester StaffDataScope) is applied
    automatically by FlatGeoScopedViewSetMixin via this model's own flat-geo
    columns, which are populated from the parent trip assignment on save
    (G1/G2/B2).
    """

    queryset = TripAttendance.objects.all()
    serializer_class = TripAttendanceSerializer
    permission_resource = "TripAttendance"
    swagger_tags = ["Desktop / Trip Attendance"]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @staticmethod
    def _resolve_user(request):
        user = getattr(request, "user", None)
        if getattr(user, "unique_id", None):
            return user

        raw_request = getattr(request, "_request", None)
        raw_user = getattr(raw_request, "user", None)
        if getattr(raw_user, "unique_id", None):
            return raw_user

        return None

    @staticmethod
    def _verify_face(staff, photo):
        if not photo:
            return False, "photo is required"

        if not staff.photo:
            return False, "Staff photo is not registered"

        source_path = staff.photo.path
        if not os.path.exists(source_path):
            return False, "Registered face image not found"

        url = "http://125.17.238.158:8000/api/v1/verification/verify"
        headers = {"x-api-key": "c4bb2855-e789-45e4-8dcd-903f03e03f2f"}

        try:
            photo.seek(0)
            with open(source_path, "rb") as src:
                files = {
                    "source_image": ("source.jpg", src, "image/jpeg"),
                    "target_image": (
                        photo.name,
                        photo,
                        getattr(photo, "content_type", "image/jpeg"),
                    ),
                }
                resp = requests.post(url, headers=headers, files=files, timeout=30)

            try:
                res = resp.json()
            except Exception:
                return False, "Face API invalid response"

            try:
                score = float(res["result"][0]["face_matches"][0]["similarity"])
            except Exception:
                return False, "Face not detected"

            if score < 0.95:
                return False, "Face similarity not matched"

            photo.seek(0)
            return True, None
        except Exception:
            return False, "Face verification failed"

    def create(self, request, *args, **kwargs):
        user = self._resolve_user(request)
        if not user:
            return Response(
                {"detail": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        role = (
            user.staffusertype_id.name.lower()
            if user and user.staffusertype_id
            else None
        )

        data = request.data.copy()
        if request.FILES.get("photo"):
            data["photo"] = request.FILES.get("photo")
        data["attendance_time"] = timezone.now()

        if data.get("daily_trip_assignment_id") and not data.get("vehicle_id"):
            trip = DailyTripAssignment.objects.filter(
                unique_id=data["daily_trip_assignment_id"]
            ).select_related("vehicle_id").first()
            if trip and trip.vehicle_id:
                data["vehicle_id"] = trip.vehicle_id.unique_id
        if not data.get("daily_trip_assignment_id"):
            trip = (
                DailyTripAssignment.objects
                .filter(
                    staff_template_id__operator_id_id=user.unique_id,
                    status__in=[
                        DailyTripAssignment.STATUS_IN_PROGRESS,
                        DailyTripAssignment.STATUS_SCHEDULED,
                    ],
                )
                .order_by("-created_at")
                .select_related("vehicle_id")
                .first()
            )
            if not trip:
                trip = (
                    DailyTripAssignment.objects
                    .filter(
                        staff_template_id__driver_id_id=user.unique_id,
                        status__in=[
                            DailyTripAssignment.STATUS_IN_PROGRESS,
                            DailyTripAssignment.STATUS_SCHEDULED,
                        ],
                    )
                    .order_by("-created_at")
                    .select_related("vehicle_id")
                    .first()
                )
            if not trip:
                return Response(
                    {"detail": "No active daily trip assignment found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            data["daily_trip_assignment_id"] = trip.unique_id
            data["vehicle_id"] = trip.vehicle_id.unique_id if trip.vehicle_id else None

        if role in {"operator", "driver"}:
            if data.get("staff_id") and data.get("staff_id") != user.unique_id:
                return Response(
                    {"detail": "You can only submit your own attendance."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            data["staff_id"] = user.unique_id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        if data.get("source") == "MOBILE":
            photo = request.FILES.get("photo")
            ok, error = self._verify_face(user.staff_id, photo)
            if not ok:
                return Response(
                    {"detail": error},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        instance = serializer.save()

        return Response(
            TripAttendanceSerializer(instance).data,
            status=status.HTTP_201_CREATED
        )

    def update(self, request, *args, **kwargs):
        immutable_fields = {"daily_trip_assignment_id", "staff_id", "vehicle_id", "attendance_time"}
        if immutable_fields.intersection(request.data.keys()):
            return Response(
                {"detail": "Trip, staff, vehicle, and attendance_time cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = self._resolve_user(request)
        if not user:
            return Response(
                {"detail": "Authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        role = (
            user.staffusertype_id.name.lower()
            if user and user.staffusertype_id
            else None
        )

        if role in {"operator", "driver"}:
            instance = self.get_object()
            if instance.staff_id != user.unique_id:
                return Response(
                    {"detail": "You can only update your own attendance."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        return super().update(request, *args, **kwargs)

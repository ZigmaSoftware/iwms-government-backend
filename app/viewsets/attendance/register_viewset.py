import os
from datetime import datetime

import requests
from django.conf import settings
from django.db import transaction
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.user_creations.staffcreation import Staffcreation


FACE_VERIFY_URL = "http://125.17.238.158:8000/api/v1/verification/verify"
FACE_VERIFY_HEADERS = {"x-api-key": "c4bb2855-e789-45e4-8dcd-903f03e03f2f"}


def _save_registration_image(emp_id, source_image, timestamp):
    folder = os.path.join(settings.MEDIA_ROOT, "attendance", "registration")
    os.makedirs(folder, exist_ok=True)
    filename = f"{emp_id}_{timestamp}.jpg"
    absolute_path = os.path.join(folder, filename)
    with open(absolute_path, "wb+") as destination:
        for chunk in source_image.chunks():
            destination.write(chunk)
    return f"attendance/registration/{filename}", absolute_path


def _validate_single_reference_face(image_path):
    try:
        with open(image_path, "rb") as source, open(image_path, "rb") as target:
            response = requests.post(
                FACE_VERIFY_URL,
                headers=FACE_VERIFY_HEADERS,
                files={
                    "source_image": ("source.jpg", source, "image/jpeg"),
                    "target_image": ("target.jpg", target, "image/jpeg"),
                },
                timeout=30,
            )
        data = response.json()
    except Exception as exc:
        return False, f"Face validation failed. Please try again. ({exc})"

    message = str(data.get("message") or "").lower() if isinstance(data, dict) else ""
    code = data.get("code") if isinstance(data, dict) else None
    if code == 31 or "more than one face" in message:
        return False, "More than one face detected. Register with only one face in the frame."

    try:
        data["result"][0]["source_image_face"]
        data["result"][0]["face_matches"][0]
    except (KeyError, IndexError, TypeError):
        return False, "Face not detected clearly. Register in good light, facing the camera."
    return True, None


def _find_staff(identifier):
    return Staffcreation.objects.filter(staff_unique_id=identifier).first() or Staffcreation.objects.filter(
        emp_id=identifier
    ).first()


class RegisterViewSet(ViewSet):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "emp_id",
                openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=True,
                description="Staff unique ID or employee ID (EMP-000001)",
            ),
            openapi.Parameter(
                "source_image", openapi.IN_FORM, type=openapi.TYPE_FILE, required=True
            ),
        ]
    )
    def create(self, request):
        identifier = str(request.data.get("emp_id") or "").strip()
        source_image = request.FILES.get("source_image")
        if not identifier or not source_image:
            return Response(
                {"error": "emp_id and source_image required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        staff = _find_staff(identifier)
        if not staff:
            return Response({"error": "Staff not found"}, status=status.HTTP_404_NOT_FOUND)
        if not staff.emp_id:
            staff._ensure_emp_id()
            staff.save(update_fields=["emp_id"])

        relative_path, absolute_path = _save_registration_image(
            staff.emp_id,
            source_image,
            datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
        )
        valid, error = _validate_single_reference_face(absolute_path)
        if not valid:
            try:
                os.remove(absolute_path)
            except OSError:
                pass
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        old_image = staff.attendance_reg_image.name if staff.attendance_reg_image else None
        with transaction.atomic():
            staff.attendance_reg_image.name = relative_path
            staff.save(update_fields=["attendance_reg_image"])

        if old_image and old_image != relative_path:
            staff.attendance_reg_image.storage.delete(old_image)

        return Response(
            {
                "message": "Attendance registration saved successfully",
                "staff_unique_id": staff.staff_unique_id,
                "emp_id": staff.emp_id,
                "name": staff.employee_name,
                "department": staff.department or "",
                "image": staff.attendance_reg_image.url,
                "qr": staff.qr_code.url if staff.qr_code else None,
            },
            status=status.HTTP_200_OK,
        )

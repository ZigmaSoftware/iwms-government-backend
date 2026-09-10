"""Attendance face registration.

Saves a staff member's reference selfie and, on providers that compare face
vectors, the embedding derived from it. Which engine validates the photo is
decided by `FACE_RECOGNITION_PROVIDER` in `.env` (see
`app/services/face_recognition/__init__.py`); this viewset never names one.

The HTTP contract is unchanged from the CompreFace-only version — same URL,
same `emp_id` + `source_image` form fields, same response keys — so the
mobile app works against either engine with no rebuild.
"""

import os
from datetime import datetime

from django.conf import settings
from django.db import transaction
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.services import face_recognition


def _save_registration_image(emp_id, image_bytes, timestamp):
    """Write the already-read upload to MEDIA_ROOT/attendance/registration/.

    Takes bytes rather than the UploadedFile because the caller has to read
    the stream to hand it to the face provider first, and an upload stream
    can only be consumed once — re-reading it with `.chunks()` here would
    write a zero-byte file.
    """
    folder = os.path.join(settings.MEDIA_ROOT, "attendance", "registration")
    os.makedirs(folder, exist_ok=True)
    filename = f"{emp_id}_{timestamp}.jpg"
    absolute_path = os.path.join(folder, filename)
    with open(absolute_path, "wb") as destination:
        destination.write(image_bytes)
    return f"attendance/registration/{filename}", absolute_path


def _find_staff(identifier):
    return Staffcreation.objects.filter(staff_unique_id=identifier).first() or Staffcreation.objects.filter(
        emp_id=identifier
    ).first()


class RegisterViewSet(ViewSet):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description=(
            "Register a staff member's reference face for attendance. Validated "
            "by whichever engine FACE_RECOGNITION_PROVIDER selects."
        ),
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
        ],
        consumes=["multipart/form-data"],
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

        # Read once: the validator needs the bytes and the file also has to be
        # written to disk, and an UploadedFile stream can only be consumed once.
        image_bytes = source_image.read()

        provider = face_recognition.get_provider()
        try:
            reference = provider.validate_reference(image_bytes)
        except face_recognition.FaceUnavailable as exc:
            # The engine is down/misconfigured — not a bad photo. Answer 503 so
            # the app can tell the user to retry rather than blame their face.
            return Response({"error": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except face_recognition.FaceError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Only written once the photo has been accepted, so a rejected
        # registration leaves no orphan file behind (the old flow saved first
        # and deleted on failure).
        relative_path, _absolute_path = _save_registration_image(
            staff.emp_id,
            image_bytes,
            datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
        )

        old_image = staff.attendance_reg_image.name if staff.attendance_reg_image else None
        with transaction.atomic():
            staff.attendance_reg_image.name = relative_path
            # Always overwrite, including with None: a stale vector from the
            # previous photo (or from another provider) must never outlive the
            # image it was derived from.
            staff.face_embedding = reference.embedding
            staff.save(update_fields=["attendance_reg_image", "face_embedding"])

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
                "provider": provider.name,
            },
            status=status.HTTP_200_OK,
        )

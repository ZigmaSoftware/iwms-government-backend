import os

from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from django.conf import settings
from django.db import IntegrityError, transaction
from datetime import datetime
from dateutil import parser

from app.models.user_creations.attendance import Employee
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.qr import generate_qr


def _clean_text(value, fallback=""):
    value = fallback if value is None else value
    return str(value).strip()


class RegisterViewSet(ViewSet):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "emp_id", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=True,
                description="staff_unique_id (ST-xxxx)"
            ),
            openapi.Parameter(
                "source_image", openapi.IN_FORM,
                type=openapi.TYPE_FILE,
                required=True
            ),
            openapi.Parameter(
                "name", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                "department", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                "dob", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                "blood_group", openapi.IN_FORM,
                type=openapi.TYPE_STRING,
                required=False
            ),
        ]
    )
    def create(self, request):
        emp_id = request.data.get("emp_id")
        source_image = request.FILES.get("source_image")

        if not emp_id or not source_image:
            return Response(
                {"error": "emp_id and source_image required"},
                status=400
            )

        staff = Staffcreation.objects.filter(
            staff_unique_id=emp_id
        ).first()

        if not staff:
            return Response({"error": "Staff not found"}, status=404)

        existing = Employee.objects.filter(
            staff=staff
        ).first()

        if existing:
            # Handle potential binary data in image_path and qr_code_path
            image_value = existing.image_path
            qr_value = existing.qr_code_path
            
            # If the field contains binary data, convert to empty string
            if isinstance(image_value, (bytes, bytearray, memoryview)):
                image_value = ""
            if isinstance(qr_value, (bytes, bytearray, memoryview)):
                qr_value = ""
            
            return Response({
                "message": "Employee already registered",
                "emp_id": emp_id,
                "name": existing.name,
                "department": existing.department,
                "image": image_value,
                "qr": qr_value,
            })

        name = _clean_text(
            request.data.get("name"),
            fallback=staff.employee_name or staff.username or emp_id,
        )
        department = _clean_text(
            request.data.get("department"),
            fallback=staff.department or "",
        )

        try:
            dob = (
                parser.parse(request.data.get("dob")).date()
                if request.data.get("dob")
                else None
            )
        except (TypeError, ValueError, OverflowError, parser.ParserError):
            return Response({"error": "Invalid dob"}, status=400)

        blood_group = _clean_text(request.data.get("blood_group"))

        # Clamp to the model's column widths — MySQL in strict mode rejects
        # any overflow with a DataError that would surface as a raw 500.
        name = name[:100]
        department = department[:100]
        blood_group = blood_group[:10]

        # Ensure display ID exists
        if not staff.emp_id:
            staff._ensure_emp_id()
            staff.save(update_fields=["emp_id"])

        # Employee.emp_id is unique, but _ensure_emp_id only dedupes against the
        # staff table — so a value already claimed by ANOTHER employee row would
        # blow up Employee.objects.create() with an IntegrityError (→ 500).
        clash = Employee.objects.filter(emp_id=staff.emp_id).first()
        if clash and str(clash.staff_id) != str(staff.staff_unique_id):
            return Response(
                {
                    "error": "This employee ID is already registered to another staff member.",
                    "emp_id": staff.emp_id,
                },
                status=409,
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Any failure past this point (bad filename, unwritable MEDIA_ROOT,
        # duplicate row, DB constraint) is returned as parseable JSON so the app
        # shows a real message instead of an unhandled HTML 500.
        try:
            qr_filename = generate_qr(staff.emp_id, name, timestamp)

            emp_image_folder = os.path.join(settings.MEDIA_ROOT, "emp_image")
            os.makedirs(emp_image_folder, exist_ok=True)
            image_filename = f"{staff.emp_id}_{timestamp}.jpg"
            image_path = os.path.join(emp_image_folder, image_filename)
            with open(image_path, "wb+") as f:
                for chunk in source_image.chunks():
                    f.write(chunk)
            relative_image_path = f"emp_image/{image_filename}"

            with transaction.atomic():
                emp = Employee.objects.create(
                    emp_id=staff.emp_id,
                    staff=staff,
                    name=name,
                    department=department,
                    image_path=relative_image_path,
                    qr_code_path=qr_filename,
                    dob=dob,
                    blood_group=blood_group,
                )
        except IntegrityError:
            # Concurrent/duplicate registration — return the existing profile
            # rather than failing the enrolment.
            existing = Employee.objects.filter(staff=staff).first()
            if existing:
                return Response({
                    "message": "Employee already registered",
                    "emp_id": emp_id,
                    "name": existing.name,
                    "department": existing.department,
                    "image": existing.image_path
                    if isinstance(existing.image_path, str) else "",
                    "qr": existing.qr_code_path
                    if isinstance(existing.qr_code_path, str) else "",
                })
            return Response(
                {"error": "Could not register (duplicate employee ID).",
                 "emp_id": staff.emp_id},
                status=409,
            )
        except Exception as exc:
            return Response(
                {"error": "Registration failed while saving the selfie/QR.",
                 "detail": str(exc)},
                status=500,
            )

        return Response({
            "message": "Employee registered successfully",
            "emp_id": emp_id,
            "name": emp.name,
            "department": emp.department,
            "image": relative_image_path,
            "qr": qr_filename,
        })

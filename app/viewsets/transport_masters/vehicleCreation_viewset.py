
import csv
import io

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet
from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.transport_masters.fuel import Fuel
from app.serializers.transport_masters.vehicleCreation_serializer import VehicleCreationSerializer
from app.utils.audit_mixin import AuditViewSetMixin

class VehicleCreationViewSet(AuditViewSetMixin,CompanyScopedViewSet):
    queryset = VehicleCreation.objects.filter(is_deleted=False)
    serializer_class = VehicleCreationSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "vehicles"

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_url_kwarg = self.lookup_url_kwarg or lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        queryset = self.filter_queryset(self.get_queryset())

        obj = get_object_or_404(queryset, **{lookup_field: lookup_value})

        self.check_object_permissions(self.request, obj)
        return obj

    # -------------------------------------------------------------
    # Bulk vehicle creation helpers
    # -------------------------------------------------------------

    def _find_vehicle_type(self, raw_value: str | None) -> VehicleTypeCreation | None:
        if not raw_value:
            return None

        value = str(raw_value).strip()
        return VehicleTypeCreation.objects.filter(
            is_deleted=False
        ).filter(
            Q(unique_id__iexact=value) | Q(vehicleType__iexact=value)
        ).first()

    def _find_fuel(self, raw_value: str | None) -> Fuel | None:
        if not raw_value:
            return None

        value = str(raw_value).strip()
        return Fuel.objects.filter(
            is_deleted=False
        ).filter(
            Q(unique_id__iexact=value) | Q(fuel_type__iexact=value)
        ).first()

    # =========================================================
    # ✅ BULK UPLOAD – VEHICLE CREATION
    # =========================================================

    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        file = request.FILES.get("file")

        if not file:
            return Response({"error": "CSV file is required"}, status=400)

        decoded_file = None
        try:
            decoded_file = file.read().decode("utf-8")
        except Exception as exc:
            return Response({"error": "Unable to decode CSV file", "detail": str(exc)}, status=400)

        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        success_count = 0
        errors: list[dict[str, object]] = []

        for index, row in enumerate(reader, start=1):
            vehicle_no = (row.get("vehicle_no") or "").strip()

            if not vehicle_no:
                errors.append({"row": index, "error": "vehicle_no is required"})
                continue

            vehicle_type = self._find_vehicle_type(row.get("vehicle_type"))
            if row.get("vehicle_type") and not vehicle_type:
                errors.append({"row": index, "error": f"Invalid vehicle_type: {row.get('vehicle_type')}"})
                continue

            fuel = self._find_fuel(row.get("fuel_type"))
            if row.get("fuel_type") and not fuel:
                errors.append({"row": index, "error": f"Invalid fuel_type: {row.get('fuel_type')}"})
                continue

            condition_value = (row.get("vehicle_condition") or "").strip().upper()
            if condition_value and condition_value not in VehicleCreation.ConditionChoices.values:
                allowed = ", ".join(VehicleCreation.ConditionChoices.values)
                errors.append({"row": index, "error": f"vehicle_condition must be one of: {allowed}"})
                continue

            payload = {
                "vehicle_no": vehicle_no,
                "vehicle_type_id": vehicle_type.unique_id if vehicle_type else None,
                "fuel_type_id": fuel.unique_id if fuel else None,
                "capacity": row.get("capacity") or None,
                "mileage_per_liter": row.get("mileage_per_liter") or None,
                "service_record": row.get("service_record") or None,
                "vehicle_insurance": row.get("vehicle_insurance") or None,
                "insurance_expiry_date": row.get("insurance_expiry_date") or None,
                "vehicle_condition": condition_value or None,
                "fuel_tank_capacity": row.get("fuel_tank_capacity") or None,
            }
            is_active_value = (row.get("is_active") or "").strip().lower()
            if is_active_value:
                payload["is_active"] = is_active_value in {"true", "1", "yes", "y"}

            serializer = self.get_serializer(data=payload)

            if serializer.is_valid():
                serializer.save()
                success_count += 1
            else:
                errors.append({"row": index, "error": serializer.errors})

        return Response({
            "message": "Vehicle bulk upload completed",
            "success_count": success_count,
            "errors": errors,
        })

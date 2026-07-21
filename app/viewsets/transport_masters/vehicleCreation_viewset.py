
import csv
import io

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from app.models.transport_masters.vehicleCreation import VehicleCreation
from app.models.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from app.models.transport_masters.fuel import Fuel
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.serializers.transport_masters.vehicleCreation_serializer import VehicleCreationSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import filter_flat_geo_queryset_by_params

class VehicleCreationViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    queryset = VehicleCreation.objects.filter(is_deleted=False)
    serializer_class = VehicleCreationSerializer
    lookup_field = "unique_id"

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "vehicles"

    # -------------------------------------------------------------
    # Scope the default list/retrieve queryset by geo query params
    # (state_id/district_id/area_type_id/corporation_id/etc.), same
    # convention as CollectionPointViewSet/BinsViewSet/CustomerCreationViewSet.
    # Lets callers like Trip Plan's vehicle dropdown fetch only the vehicles
    # for a given local body instead of downloading every vehicle.
    # -------------------------------------------------------------
    def get_queryset(self):
        queryset = super().get_queryset()

        for field in (
            "state_id",
            "district_id",
            "area_type_id",
            "corporation_id",
            "municipality_id",
            "town_panchayat_id",
            "panchayat_union_id",
            "panchayat_id",
        ):
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})

        return queryset

    def get_object(self):
        lookup_field = self.lookup_field
        lookup_url_kwarg = self.lookup_url_kwarg or lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        queryset = self.filter_queryset(self.get_queryset())

        obj = get_object_or_404(queryset, **{lookup_field: lookup_value})

        self.check_object_permissions(self.request, obj)
        return obj

    # -------------------------------------------------------------
    # Available vehicles — scoped to a government hierarchy (state/
    # district/area_type/local body) and active only. Consumed by Trip
    # Plan's vehicle dropdown so it only lists vehicles that belong to
    # the trip's own location, e.g. `?district_id=...&panchayat_id=...`.
    # -------------------------------------------------------------
    @action(detail=False, methods=["get"], url_path="available")
    def available(self, request):
        queryset = filter_flat_geo_queryset_by_params(
            self.get_queryset().filter(is_active=True), request.query_params
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def _find_location(self, model, raw_value: str | None):
        if not raw_value:
            return None
        value = str(raw_value).strip()
        return model.objects.filter(is_deleted=False, unique_id__iexact=value).first()

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

            state = self._find_location(State, row.get("state_id"))
            district = self._find_location(District, row.get("district_id"))
            area_type = self._find_location(AreaType, row.get("area_type_id"))
            corporation = self._find_location(Corporation, row.get("corporation_id"))
            municipality = self._find_location(Municipality, row.get("municipality_id"))
            town_panchayat = self._find_location(TownPanchayat, row.get("town_panchayat_id"))
            panchayat_union = self._find_location(PanchayatUnion, row.get("panchayat_union_id"))
            panchayat = self._find_location(Panchayat, row.get("panchayat_id"))

            payload = {
                "vehicle_no": vehicle_no,
                "vehicle_type_id": vehicle_type.unique_id if vehicle_type else None,
                "fuel_type_id": fuel.unique_id if fuel else None,
                "state_id": state.unique_id if state else None,
                "district_id": district.unique_id if district else None,
                "area_type_id": area_type.unique_id if area_type else None,
                "corporation_id": corporation.unique_id if corporation else None,
                "municipality_id": municipality.unique_id if municipality else None,
                "town_panchayat_id": town_panchayat.unique_id if town_panchayat else None,
                "panchayat_union_id": panchayat_union.unique_id if panchayat_union else None,
                "panchayat_id": panchayat.unique_id if panchayat else None,
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

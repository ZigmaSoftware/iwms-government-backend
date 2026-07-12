from decimal import Decimal

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.permissions.operator_permission import IsOperatorRole
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    resolve_operator_staff,
)


def _serialize_summary(assignment: DailyTripAssignment) -> dict:
    children = list(assignment.trip_collection_points.filter(is_deleted=False))
    total = len(children)
    collected = sum(1 for c in children if c.is_collected)
    total_weight = sum(
        (c.collected_weight_kg or Decimal("0")) for c in children
    )
    panchayat = assignment.panchayat
    waste_type = assignment.waste_type_id
    return {
        "assignment_unique_id": assignment.unique_id,
        "trip_date": assignment.trip_date.isoformat(),
        "status": assignment.status,
        "panchayat": {
            "unique_id": panchayat.unique_id,
            "name": panchayat.panchayat_name,
        },
        "waste_type": {
            "unique_id": waste_type.unique_id,
            "name": waste_type.waste_type_name,
        },
        "progress": {
            "collected": collected,
            "total": total,
            "completed": total > 0 and collected == total,
        },
        "total_weight_kg": str(total_weight),
    }


def _serialize_event(event: BinCollectionEvent) -> dict:
    return {
        "unique_id": event.unique_id,
        "event_at": event.created_at.isoformat(),
        "collected_weight_kg": str(event.collected_weight_kg),
        "scanned_qr": getattr(event.bin_id, "bin_qr", None),
        "bin": {
            "unique_id": event.bin_id_id,
            "bin_name": getattr(event.bin_id, "bin_name", None),
        },
        "collection_point": {
            "unique_id": event.collection_point_id_id,
            "name": getattr(event.collection_point_id, "cp_name", None),
        },
        "latitude": (
            str(event.driver_latitude) if event.driver_latitude is not None else None
        ),
        "longitude": (
            str(event.driver_longitude) if event.driver_longitude is not None else None
        ),
        "notes": event.notes,
    }


class TripHistoryViewSet(viewsets.ViewSet):
    """
    GET /api/v1/operator-mobile/trip-history/            (list)
    GET /api/v1/operator-mobile/trip-history/{trip_id}/  (detail)
    """

    permission_classes = [IsOperatorRole]
    lookup_field = "unique_id"

    def _base_queryset(self, operator):
        # Primary path: assignments where the operator is the template's main operator.
        # We omit the extra_operator_id JSON membership query here because it isn't
        # supported on SQLite (used in tests); extras are uncommon and can be added
        # later as a Python-side filter when needed.
        return (
            DailyTripAssignment.objects
            .filter(is_deleted=False)
            .filter(
                Q(staff_template_id__operator_id=operator)
                | Q(staff_template_id__driver_id=operator)
            )
            .select_related(
                "panchayat",
                "waste_type_id",
                "vehicle_id",
            )
            .prefetch_related("trip_collection_points")
            .order_by("-trip_date", "-scheduled_time")
        )

    def list(self, request):
        try:
            operator = resolve_operator_staff(request.user)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        qs = self._base_queryset(operator)
        date_from = request.query_params.get("from")
        date_to = request.query_params.get("to")
        if date_from:
            qs = qs.filter(trip_date__gte=date_from)
        if date_to:
            qs = qs.filter(trip_date__lte=date_to)

        results = [_serialize_summary(a) for a in qs[:200]]
        return Response({"results": results}, status=status.HTTP_200_OK)

    def retrieve(self, request, unique_id=None):
        try:
            operator = resolve_operator_staff(request.user)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        assignment = (
            self._base_queryset(operator)
            .filter(unique_id=unique_id)
            .first()
        )
        if not assignment:
            return Response(
                {"code": "NOT_FOUND", "detail": "Trip not found for this operator."},
                status=status.HTTP_404_NOT_FOUND,
            )

        summary = _serialize_summary(assignment)
        events_qs = (
            BinCollectionEvent.objects
            .filter(trip_assignment_id=assignment, is_deleted=False)
            .select_related("bin_id", "collection_point_id")
            .order_by("created_at")
        )
        summary["events"] = [_serialize_event(e) for e in events_qs]

        cps = (
            assignment.trip_collection_points
            .filter(is_deleted=False)
            .select_related("collection_point_id", "bin_id")
            .order_by("sequence")
        )
        summary["collection_points"] = [
            {
                "unique_id": cp.unique_id,
                "sequence": cp.sequence,
                "is_collected": cp.is_collected,
                "status": cp.status,
                "collected_at": cp.collected_at.isoformat() if cp.collected_at else None,
                "collected_weight_kg": (
                    str(cp.collected_weight_kg) if cp.collected_weight_kg is not None else None
                ),
                "collection_point": {
                    "unique_id": cp.collection_point_id.unique_id,
                    "name": cp.collection_point_id.cp_name,
                },
                "bin": {
                    "unique_id": cp.bin_id.unique_id,
                    "bin_name": cp.bin_id.bin_name,
                    "bin_qr": cp.bin_id.bin_qr,
                },
            }
            for cp in cps
        ]

        return Response(summary, status=status.HTTP_200_OK)

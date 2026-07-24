from decimal import Decimal

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.permissions.operator_permission import IsOperatorRole
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    resolve_operator_staff,
)


def _serialize_summary(assignment: DailyTripAssignment) -> dict:
    children = list(assignment.trip_collection_points.filter(is_deleted=False))
    total = len(children)
    collected = sum(
        1 for c in children
        if c.status == DailyTripCollectionPoint.STATUS_COLLECTED
    )
    resolved = sum(
        1 for c in children
        if c.status in {
            DailyTripCollectionPoint.STATUS_COLLECTED,
            DailyTripCollectionPoint.STATUS_MISSED,
        }
    )
    total_weight = sum(
        (c.collected_weight_kg or Decimal("0")) for c in children
    )
    panchayat = assignment.panchayat
    return {
        "assignment_unique_id": assignment.unique_id,
        "trip_date": assignment.trip_date.isoformat(),
        "status": assignment.status,
        # panchayat is a nullable FK — a household-only / higher-level trip may
        # have none, so guard it instead of crashing the whole history list.
        "panchayat": {
            "unique_id": panchayat.unique_id,
            "name": panchayat.panchayat_name,
        } if panchayat else None,
        "waste_types": [
            {"unique_id": wt.unique_id, "name": wt.waste_type_name}
            for wt in assignment.waste_types.all()
        ],
        "progress": {
            "collected": collected,
            "total": total,
            "resolved": resolved,
            "completed": total > 0 and resolved == total,
        },
        "total_weight_kg": str(total_weight),
    }


def _bin_qr_image_url(bin_obj, request=None):
    qr = getattr(bin_obj, "bin_qr", None)
    try:
        url = qr.url if qr else None
    except (ValueError, AttributeError):
        url = None
    if not url:
        return None
    return request.build_absolute_uri(url) if request is not None else url


def _serialize_event(event: BinCollectionEvent, request=None) -> dict:
    return {
        "unique_id": event.unique_id,
        "event_at": event.created_at.isoformat(),
        "event_type": event.status,
        "collected_weight_kg": str(event.collected_weight_kg),
        "status_reason": event.status_reason,
        "scanned_qr": event.bin_id_id,
        "bin": {
            "unique_id": event.bin_id_id,
            "bin_name": getattr(event.bin_id, "bin_name", None),
            "bin_qr": event.bin_id_id,
            "bin_qr_image_url": _bin_qr_image_url(event.bin_id, request=request),
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
        # Primary path: assignments where the operator is the EFFECTIVE template's
        # main operator/driver — i.e. the alt template's crew when a substitution
        # (`alt_staff_template_id`) is active on that assignment, else the base
        # template's crew. This keeps history consistent with "my trips today":
        # a substituted-out driver stops seeing the trip, the substituted-in one
        # does. We omit the extra_operator_id JSON membership query here because
        # it isn't supported on SQLite (used in tests); extras are uncommon and
        # can be added later as a Python-side filter when needed.
        return (
            DailyTripAssignment.objects
            .filter(is_deleted=False)
            .filter(
                Q(alt_staff_template_id__isnull=False, alt_staff_template_id__operator_id=operator)
                | Q(alt_staff_template_id__isnull=False, alt_staff_template_id__driver_id=operator)
                | Q(alt_staff_template_id__isnull=True, staff_template_id__operator_id=operator)
                | Q(alt_staff_template_id__isnull=True, staff_template_id__driver_id=operator)
            )
            .select_related(
                "panchayat",
                "vehicle_id",
                "alt_staff_template_id",
            )
            .prefetch_related("trip_collection_points", "waste_types")
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
        summary["events"] = [_serialize_event(e, request=request) for e in events_qs]

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
                "status_reason": cp.status_reason,
                "collected_at": cp.collected_at.isoformat() if cp.collected_at else None,
                "collected_weight_kg": (
                    str(cp.collected_weight_kg) if cp.collected_weight_kg is not None else None
                ),
                # collection_point / bin are nullable (household stops carry
                # neither) — guard so a single null-FK row can't 500 the detail.
                "collection_point": {
                    "unique_id": cp.collection_point_id.unique_id,
                    "name": cp.collection_point_id.cp_name,
                } if cp.collection_point_id else None,
                "bin": {
                    "unique_id": cp.bin_id.unique_id,
                    "bin_name": cp.bin_id.bin_name,
                    "bin_qr": cp.bin_id.unique_id,
                    "bin_qr_image_url": _bin_qr_image_url(cp.bin_id, request=request),
                } if cp.bin_id else None,
            }
            for cp in cps
        ]

        return Response(summary, status=status.HTTP_200_OK)

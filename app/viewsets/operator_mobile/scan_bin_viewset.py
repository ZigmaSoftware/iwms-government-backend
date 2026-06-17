from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.permissions.operator_permission import IsOperatorRole
from app.serializers.operator_mobile.scan_serializers import (
    ScanBinRequestSerializer,
)
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    build_scan_context,
    maybe_resolve_driver,
    progress_payload,
    resolve_operator_staff,
    serialize_assignment_brief,
    serialize_bin_brief,
    serialize_cp_brief,
    serialize_trip_cp_brief,
)


class ScanBinViewSet(viewsets.ViewSet):
    """POST /api/v1/operator-mobile/scan-bin/"""

    permission_classes = [IsOperatorRole]

    def create(self, request):
        serializer = ScanBinRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            operator = resolve_operator_staff(request.user)
            ctx = build_scan_context(payload["bin_qr"], operator)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        weight = payload["weight_kg"]
        vehicle = ctx.assignment.vehicle_id
        if vehicle and vehicle.capacity and Decimal(weight) > Decimal(vehicle.capacity):
            return Response(
                {
                    "code": "WEIGHT_EXCEEDS_CAPACITY",
                    "detail": (
                        f"Weight {weight} kg exceeds vehicle capacity "
                        f"{vehicle.capacity} kg."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                self._ensure_assignment_in_progress(ctx.assignment)

                ctx.trip_cp.mark_collected(
                    weight_kg=weight,
                    collected_by=operator,
                )

                event = BinCollectionEvent.objects.create(
                    trip_assignment_id=ctx.assignment,
                    trip_collection_point_id=ctx.trip_cp,
                    collection_point_id=ctx.bin.collection_point_id,
                    bin_id=ctx.bin,
                    panchayat_id=ctx.assignment.panchayat_id,
                    waste_type_id=ctx.assignment.waste_type_id,
                    vehicle_id=ctx.assignment.vehicle_id,
                    operator_id=operator,
                    driver_id=maybe_resolve_driver(ctx.assignment),
                    collected_weight_kg=weight,
                    scanned_qr=payload["bin_qr"],
                    latitude=payload.get("latitude"),
                    longitude=payload.get("longitude"),
                    notes=payload.get("notes"),
                )

                ctx.assignment.refresh_from_db()
                progress = progress_payload(ctx.assignment)
                if progress["completed"]:
                    self._upsert_trip_log(ctx.assignment, operator)
        except OperatorFlowError as exc:
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=exc.http_status,
            )

        ctx.trip_cp.refresh_from_db()

        return Response(
            {
                "bin": serialize_bin_brief(ctx.bin),
                "collection_point": serialize_cp_brief(ctx.bin.collection_point_id),
                "trip_collection_point": serialize_trip_cp_brief(ctx.trip_cp),
                "assignment": serialize_assignment_brief(ctx.assignment),
                "trip_progress": progress,
                "event": {
                    "unique_id": event.unique_id,
                    "event_at": event.event_at.isoformat(),
                    "collected_weight_kg": str(event.collected_weight_kg),
                },
            },
            status=status.HTTP_201_CREATED,
        )

    def _ensure_assignment_in_progress(self, assignment: DailyTripAssignment):
        if assignment.status in (
            DailyTripAssignment.STATUS_SCHEDULED,
        ):
            now = timezone.localtime().time()
            assignment.status = DailyTripAssignment.STATUS_IN_PROGRESS
            update_fields = ["status", "updated_at"]
            if not assignment.actual_start_time:
                assignment.actual_start_time = now
                update_fields.append("actual_start_time")
            assignment.save(update_fields=update_fields)

    def _upsert_trip_log(self, assignment: DailyTripAssignment, operator):
        children = assignment.trip_collection_points.filter(is_deleted=False)
        total_weight = sum(
            (c.collected_weight_kg or Decimal("0")) for c in children
        )

        existing = DailyTripLog.objects.filter(trip_assignment_id=assignment).first()
        if existing:
            existing.collected_weight_kg = total_weight
            existing.log_status = DailyTripLog.LOG_STATUS_SUBMITTED
            existing.save()
            return

        DailyTripLog.objects.create(
            trip_assignment_id=assignment,
            collected_weight_kg=total_weight,
            log_status=DailyTripLog.LOG_STATUS_SUBMITTED,
            remarks="Auto-generated from operator-mobile completion.",
        )

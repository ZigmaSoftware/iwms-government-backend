from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.response import Response

from app.models.schedule_masters.secondary_bin_collection_event import BinCollectionEvent
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.permissions.operator_permission import IsOperatorRole
from app.serializers.operator_mobile.scan_serializers import (
    ScanBinRequestSerializer,
)
from app.utils.audit_mixin import log_common_audit, serialize_instance_for_audit
from app.utils.hierarchy import node_for_flat_geo
from app.viewsets.operator_mobile.helpers import (
    OperatorFlowError,
    build_scan_context,
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

        action = payload["action"]
        weight = payload.get("weight_kg")
        vehicle = ctx.assignment.vehicle_id
        if (
            action == ScanBinRequestSerializer.ACTION_COLLECT
            and vehicle
            and vehicle.capacity
            and Decimal(weight) > Decimal(vehicle.capacity)
        ):
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

                if action == ScanBinRequestSerializer.ACTION_COLLECT:
                    ctx.trip_cp.mark_collected(
                        weight_kg=weight,
                        collected_by=operator,
                    )
                    event_status = BinCollectionEvent.STATUS_COLLECTED
                    event_weight = weight
                    status_reason = None
                else:
                    if action == ScanBinRequestSerializer.ACTION_COLLECT_LATER:
                        cp_status = DailyTripCollectionPoint.STATUS_SKIPPED
                        event_status = BinCollectionEvent.STATUS_COLLECT_LATER
                    else:
                        cp_status = DailyTripCollectionPoint.STATUS_MISSED
                        event_status = BinCollectionEvent.STATUS_NOT_COLLECTED

                    status_reason = payload["status_reason"]
                    ctx.trip_cp.mark_status(
                        status=cp_status,
                        reason=status_reason,
                        latitude=payload.get("latitude"),
                        longitude=payload.get("longitude"),
                    )
                    event_weight = Decimal("0.00")

                event = self._create_event(
                    ctx=ctx,
                    action=action,
                    event_status=event_status,
                    weight=event_weight,
                    latitude=payload.get("latitude"),
                    longitude=payload.get("longitude"),
                    notes=payload.get("notes"),
                    status_reason=status_reason,
                )

                log_common_audit(
                    request,
                    module_name="transport-masters",
                    endpoint_name="bin-collection-event",
                    instance=event,
                    previous_data=None,
                    new_data=serialize_instance_for_audit(event),
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
                "bin": serialize_bin_brief(ctx.bin, request=request),
                "collection_point": serialize_cp_brief(ctx.bin.collection_point_id),
                "trip_collection_point": serialize_trip_cp_brief(ctx.trip_cp),
                "assignment": serialize_assignment_brief(ctx.assignment),
                "trip_progress": progress,
                "event": {
                    "unique_id": event.unique_id,
                    "event_at": event.created_at.isoformat(),
                    "event_type": event.status,
                    "collected_weight_kg": str(event.collected_weight_kg),
                    "status_reason": event.status_reason,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    def _create_event(
        self,
        *,
        ctx,
        action,
        event_status,
        weight,
        latitude,
        longitude,
        notes,
        status_reason,
    ):
        event_notes = notes
        if action != ScanBinRequestSerializer.ACTION_COLLECT and not event_notes:
            event_notes = status_reason

        return BinCollectionEvent.objects.create(
            trip_assignment_id=ctx.assignment,
            trip_collection_point_id=ctx.trip_cp,
            collection_point_id=ctx.bin.collection_point_id,
            bin_id=ctx.bin,
            # Hierarchy visibility: stamp the audit row with the
            # collection point's location node so scope filtering works.
            location_node=node_for_flat_geo(ctx.bin.collection_point_id),
            waste_type_id=ctx.bin.wastetype_id,
            vehicle_id=ctx.assignment.vehicle_id,
            status=event_status,
            status_reason=status_reason,
            collected_weight_kg=weight,
            driver_latitude=latitude,
            driver_longitude=longitude,
            notes=event_notes,
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
        log_status = (
            DailyTripLog.LOG_STATUS_SUBMITTED
            if total_weight > 0
            else DailyTripLog.LOG_STATUS_DRAFT
        )
        remarks = (
            "Auto-generated from operator-mobile completion."
            if total_weight > 0
            else "Auto-generated from operator-mobile completion; no collected bin weight."
        )
        if existing:
            # A verified log is read-only; don't fail the scan trying to update it.
            if existing.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
                return
            existing.collected_weight_kg = total_weight
            existing.log_status = log_status
            existing.remarks = existing.remarks or remarks
            existing.save()
            return

        DailyTripLog.objects.create(
            trip_assignment_id=assignment,
            collected_weight_kg=total_weight,
            log_status=log_status,
            remarks=remarks,
        )

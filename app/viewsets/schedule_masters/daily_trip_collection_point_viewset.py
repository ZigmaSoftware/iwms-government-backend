from decimal import Decimal
import hashlib

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q, Sum
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_log import DailyTripLog
from app.models.schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from app.models.schedule_masters.bin_collection_event import BinCollectionEvent
from app.services.openroute_service import OpenRouteServiceError, optimize_stops, route_stops
from app.serializers.schedule_masters.daily_trip_collection_point_serializer import (
    DailyTripCollectionPointSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.viewsets.superadminmasters.company_scoped_viewset import CompanyScopedViewSet


class DailyTripCollectionPointViewSet(AuditViewSetMixin, CompanyScopedViewSet):
    serializer_class = DailyTripCollectionPointSerializer
    lookup_field = "unique_id"
    permission_resource = "DailyTripCollectionPoint"

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "daily-trip-collection-point"

    def _ensure_assignment_stops(self, assignment_id):
        assignment = (
            DailyTripAssignment.objects.select_related("trip_plan_id")
            .filter(unique_id=assignment_id, is_deleted=False)
            .first()
        )
        if not assignment or not assignment.trip_plan_id_id:
            return assignment

        existing_cp_ids = set(
            DailyTripCollectionPoint.objects.filter(
                trip_assignment_id=assignment,
                is_deleted=False,
            ).values_list("collection_point_id_id", flat=True)
        )
        plan_stops = TripPlanCollectionPoint.objects.filter(
            trip_plan_id=assignment.trip_plan_id,
            is_active=True,
            is_deleted=False,
        ).select_related("collection_point_id", "bin_id").order_by("sequence")
        for stop in plan_stops:
            if stop.collection_point_id_id in existing_cp_ids:
                continue
            DailyTripCollectionPoint.objects.create(
                trip_assignment_id=assignment,
                collection_point_id=stop.collection_point_id,
                bin_id=stop.bin_id,
                sequence=stop.sequence,
                is_collected=False,
                status=DailyTripCollectionPoint.STATUS_PENDING,
                created_by=getattr(assignment, "created_by", None),
            )
        return assignment

    def _ensure_current_stop(self, assignment):
        if not assignment or assignment.status != DailyTripAssignment.STATUS_IN_PROGRESS:
            return
        stops = DailyTripCollectionPoint.objects.filter(
            trip_assignment_id=assignment,
            is_deleted=False,
        )
        if stops.filter(status=DailyTripCollectionPoint.STATUS_IN_PROGRESS).exists():
            return
        next_stop = stops.filter(
            status=DailyTripCollectionPoint.STATUS_PENDING
        ).order_by("sequence").first()
        if next_stop:
            next_stop.status = DailyTripCollectionPoint.STATUS_IN_PROGRESS
            next_stop.save(update_fields=["status", "updated_at"])

    def _latest_vehicle_start(self, assignment):
        latest_event = (
            BinCollectionEvent.objects.filter(trip_assignment_id=assignment)
            .exclude(driver_latitude=None)
            .exclude(driver_longitude=None)
            .order_by("-created_at")
            .first()
        )
        if not latest_event:
            return None
        return [
            float(latest_event.driver_longitude),
            float(latest_event.driver_latitude),
        ]

    def _optimize_assignment(self, assignment_id, vehicle_start=None):
        assignment = self._ensure_assignment_stops(assignment_id)
        if not assignment:
            raise OpenRouteServiceError("Daily Trip Assignment was not found.")

        stops = list(
            self.get_queryset()
            .filter(trip_assignment_id__unique_id=assignment_id)
            .order_by("sequence")
        )
        completed_stops = [
            stop for stop in stops
            if stop.status == DailyTripCollectionPoint.STATUS_COLLECTED
        ]
        remaining_stops = [
            stop for stop in stops
            if stop.status != DailyTripCollectionPoint.STATUS_COLLECTED
        ]
        routable = [
            {
                "id": stop.unique_id,
                "location": [
                    float(stop.collection_point_id.longitude),
                    float(stop.collection_point_id.latitude),
                ],
            }
            for stop in remaining_stops
        ]
        latest_vehicle_start = self._latest_vehicle_start(assignment)
        resolved_vehicle_start = vehicle_start or latest_vehicle_start
        optimized = optimize_stops(routable, resolved_vehicle_start)
        by_id = {stop.unique_id: stop for stop in stops}
        with transaction.atomic():
            for index, stop in enumerate(completed_stops, start=1):
                stop.sequence = index
            for index, stop_id in enumerate(
                optimized["ordered_ids"],
                start=len(completed_stops) + 1,
            ):
                stop = by_id[stop_id]
                stop.sequence = index
            DailyTripCollectionPoint.objects.bulk_update(stops, ["sequence"])
        optimized["all_ordered_ids"] = [
            *[stop.unique_id for stop in completed_stops],
            *optimized["ordered_ids"],
        ]
        optimized["optimized_stop_count"] = len(remaining_stops)
        optimized["completed_stop_count"] = len(completed_stops)
        optimized["vehicle_no"] = getattr(assignment.vehicle_id, "vehicle_no", None)
        optimized["vehicle_start_source"] = (
            "request"
            if vehicle_start
            else "latest_gps"
            if latest_vehicle_start
            else "first_collection_point"
        )
        return optimized

    def _optimize_assignment_silently(self, assignment_id):
        try:
            self._optimize_assignment(assignment_id)
        except OpenRouteServiceError:
            # CRUD remains available if ORS is unavailable; manual optimization reports errors.
            pass

    def _upsert_trip_log_for_assignment(self, assignment):
        if not assignment:
            return

        children = assignment.trip_collection_points.filter(is_deleted=False)
        if not children.exists():
            return

        all_collected = not children.filter(is_collected=False).exists()
        total_weight = children.aggregate(total=Sum("collected_weight_kg"))["total"] or 0
        vehicle_capacity = getattr(getattr(assignment, "vehicle_id", None), "capacity", None)
        trip_capacity = getattr(getattr(assignment, "trip_plan_id", None), "max_vehicle_capacity_kg", None)
        capacity = vehicle_capacity or trip_capacity
        exceeds_capacity = (
            bool(capacity)
            and total_weight
            and Decimal(str(total_weight)) > Decimal(str(capacity))
        )
        stored_weight = None if exceeds_capacity else total_weight
        log_status = (
            DailyTripLog.LOG_STATUS_SUBMITTED
            if all_collected and stored_weight
            else DailyTripLog.LOG_STATUS_DRAFT
        )
        remarks = (
            "Auto-generated from daily trip collection points; total weight exceeds capacity."
            if exceeds_capacity
            else "Auto-generated from daily trip collection points."
        )

        log, created = DailyTripLog.objects.get_or_create(
            trip_assignment_id=assignment,
            defaults={
                "collected_weight_kg": stored_weight,
                "log_status": log_status,
                "remarks": remarks,
            },
        )
        if created or log.log_status == DailyTripLog.LOG_STATUS_VERIFIED:
            return

        log.collected_weight_kg = stored_weight
        log.log_status = log_status
        log.remarks = log.remarks or remarks
        log.save()

    def _sync_assignment_and_log(self, instance):
        if not instance:
            return
        assignment = instance.trip_assignment_id
        if instance.is_collected:
            assignment.mark_completed_if_all_cps_collected()
        self._upsert_trip_log_for_assignment(assignment)

    def get_queryset(self):
        queryset = (
            DailyTripCollectionPoint.objects.select_related(
                "trip_assignment_id",
                "trip_assignment_id__trip_plan_id",
                "collection_point_id",
                "collection_point_id__panchayat_id",
                "collection_point_id__ward_id",
                "collection_point_id__ward_id__zone_id",
                "zone_id",
                "ward_id",
                "panchayat_id",
                "bin_id",
                "bin_id__wastetype_id",
                "collected_by",
            )
            .filter(is_deleted=False)
        )

        params = self.request.query_params
        assignment = params.get("trip_assignment_id")
        collection_point = params.get("collection_point_id")
        bin_id = params.get("bin_id")
        status_value = params.get("status")
        is_collected = params.get("is_collected")
        trip_date = params.get("date") or params.get("trip_date")
        staff_template = params.get("staff_template_id")
        alt_staff_template = params.get("alt_staff_template_id")
        zone = params.get("zone_id")
        ward = params.get("ward_id")
        panchayat = params.get("panchayat_id")
        search = params.get("search")

        if assignment:
            queryset = queryset.filter(trip_assignment_id__unique_id=assignment)
        if collection_point:
            queryset = queryset.filter(collection_point_id__unique_id=collection_point)
        if bin_id:
            queryset = queryset.filter(bin_id__unique_id=bin_id)
        if status_value and getattr(self, "action", None) != "tracking":
            queryset = queryset.filter(status=status_value)
        if is_collected is not None:
            queryset = queryset.filter(
                is_collected=str(is_collected).lower() in {"1", "true", "yes"}
            )
        if trip_date and not assignment:
            queryset = queryset.filter(trip_assignment_id__trip_date=trip_date)
        if staff_template:
            queryset = queryset.filter(
                trip_assignment_id__staff_template_id__unique_id=staff_template
            )
        if alt_staff_template:
            queryset = queryset.filter(
                trip_assignment_id__alt_staff_template_id__unique_id=alt_staff_template
            )
        if zone:
            queryset = queryset.filter(zone_id__unique_id=zone)
        if ward:
            queryset = queryset.filter(ward_id__unique_id=ward)
        if panchayat:
            queryset = queryset.filter(panchayat_id__unique_id=panchayat)
        if search:
            queryset = queryset.filter(
                Q(collection_point_id__cp_name__icontains=search)
                | Q(trip_assignment_id__unique_id__icontains=search)
                | Q(bin_id__bin_name__icontains=search)
            )

        return queryset

    @action(detail=False, methods=["get"], url_path="tracking")
    def tracking(self, request):
        assignment_id = request.query_params.get("trip_assignment_id")
        if assignment_id:
            selected_assignment = self._ensure_assignment_stops(assignment_id)
            self._ensure_current_stop(selected_assignment)

        route_queryset = self.filter_queryset(self.get_queryset()).order_by(
            "trip_assignment_id", "sequence"
        )
        status_value = request.query_params.get("status")
        if status_value == DailyTripCollectionPoint.STATUS_MISSED:
            queryset = route_queryset.filter(
                status__in=[
                    DailyTripCollectionPoint.STATUS_MISSED,
                    DailyTripCollectionPoint.STATUS_SKIPPED,
                ]
            )
        else:
            queryset = route_queryset.filter(status=status_value) if status_value else route_queryset
        page = max(int(request.query_params.get("page", 1)), 1)
        page_size = min(max(int(request.query_params.get("page_size", 20)), 1), 100)
        total = queryset.count()
        start = (page - 1) * page_size
        rows = queryset[start:start + page_size]

        route_total = route_queryset.count()
        completed = route_queryset.filter(status=DailyTripCollectionPoint.STATUS_COLLECTED).count()
        in_progress = route_queryset.filter(
            status=DailyTripCollectionPoint.STATUS_IN_PROGRESS
        ).count()
        pending = route_queryset.filter(status=DailyTripCollectionPoint.STATUS_PENDING).count()
        missed = route_queryset.filter(
            status__in=[
                DailyTripCollectionPoint.STATUS_SKIPPED,
                DailyTripCollectionPoint.STATUS_MISSED,
            ]
        ).count()

        assignment = (
            route_queryset.first().trip_assignment_id
            if route_queryset.exists()
            else None
        )
        if assignment_id and not assignment:
            assignment = (
                DailyTripAssignment.objects.filter(
                    unique_id=assignment_id,
                    is_deleted=False,
                )
                .select_related("vehicle_id")
                .first()
            )
        latest_event = None
        if assignment:
            latest_event = (
                BinCollectionEvent.objects.filter(trip_assignment_id=assignment)
                .exclude(driver_latitude=None)
                .exclude(driver_longitude=None)
                .select_related("collection_point_id")
                .order_by("-created_at")
                .first()
            )
        next_stop = route_queryset.filter(
            status__in=[
                DailyTripCollectionPoint.STATUS_PENDING,
                DailyTripCollectionPoint.STATUS_IN_PROGRESS,
            ]
        ).first()

        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "summary": {
                "total": route_total,
                "completed": completed,
                "in_progress": in_progress,
                "pending": pending,
                "missed": missed,
                "completion_percentage": round((completed / route_total) * 100, 2) if route_total else 0,
            },
            "results": self.get_serializer(rows, many=True).data,
            "route_results": self.get_serializer(route_queryset[:500], many=True).data,
            "vehicle_tracking": {
                "vehicle_no": getattr(getattr(assignment, "vehicle_id", None), "vehicle_no", None),
                "current_location": None if not latest_event else {
                    "latitude": latest_event.driver_latitude,
                    "longitude": latest_event.driver_longitude,
                    "recorded_at": latest_event.created_at,
                    "collection_point": latest_event.collection_point_id.cp_name,
                },
                "next_collection_point": None if not next_stop else {
                    "unique_id": next_stop.collection_point_id.unique_id,
                    "cp_name": next_stop.collection_point_id.cp_name,
                    "latitude": next_stop.collection_point_id.latitude,
                    "longitude": next_stop.collection_point_id.longitude,
                },
                "remaining_collection_points": pending + in_progress,
            },
        })

    @action(detail=False, methods=["get"], url_path="tracking-overview")
    def tracking_overview(self, request):
        assignments = DailyTripAssignment.objects.select_related(
            "vehicle_id",
            "trip_plan_id",
        ).filter(is_deleted=False)
        company = request.query_params.get("company_id")
        project = request.query_params.get("project_id")
        trip_date = request.query_params.get("date") or request.query_params.get("trip_date")
        if trip_date:
            assignments = assignments.filter(trip_date=trip_date)
        assignments = assignments.order_by("-trip_date", "-scheduled_time")[:30]

        trips = []
        aggregate = {"total": 0, "completed": 0, "in_progress": 0, "pending": 0, "missed": 0}
        for assignment in assignments:
            self._ensure_assignment_stops(assignment.unique_id)
            self._ensure_current_stop(assignment)
            stops = list(
                DailyTripCollectionPoint.objects.select_related(
                    "collection_point_id",
                    "collection_point_id__panchayat_id",
                    "collection_point_id__ward_id",
                    "collection_point_id__ward_id__zone_id",
                    "trip_assignment_id",
                    "trip_assignment_id__trip_plan_id",
                    "bin_id",
                    "bin_id__wastetype_id",
                    "collected_by",
                )
                .filter(trip_assignment_id=assignment, is_deleted=False)
                .order_by("sequence")
            )
            if not stops:
                continue

            completed = sum(stop.status == DailyTripCollectionPoint.STATUS_COLLECTED for stop in stops)
            in_progress = sum(stop.status == DailyTripCollectionPoint.STATUS_IN_PROGRESS for stop in stops)
            pending = sum(stop.status == DailyTripCollectionPoint.STATUS_PENDING for stop in stops)
            missed = sum(
                stop.status in [
                    DailyTripCollectionPoint.STATUS_MISSED,
                    DailyTripCollectionPoint.STATUS_SKIPPED,
                ]
                for stop in stops
            )
            aggregate["total"] += len(stops)
            aggregate["completed"] += completed
            aggregate["in_progress"] += in_progress
            aggregate["pending"] += pending
            aggregate["missed"] += missed

            route_input = [
                {
                    "id": stop.unique_id,
                    "location": [
                        float(stop.collection_point_id.longitude),
                        float(stop.collection_point_id.latitude),
                    ],
                }
                for stop in stops
            ]
            vehicle_start = self._latest_vehicle_start(assignment)
            route_signature = "|".join(
                [
                    assignment.unique_id,
                    str(vehicle_start),
                    *[
                        f"{stop.unique_id}:{stop.sequence}:{stop.collection_point_id.latitude}:{stop.collection_point_id.longitude}"
                        for stop in stops
                    ],
                ]
            )
            cache_key = f"daily-trip-overview-route:{hashlib.sha1(route_signature.encode()).hexdigest()}"
            route = cache.get(cache_key)
            if route is None:
                route = route_stops(route_input, vehicle_start)
                cache.set(cache_key, route, timeout=300)
            trips.append({
                "assignment_id": assignment.unique_id,
                "trip_date": assignment.trip_date,
                "status": assignment.status,
                "vehicle_no": getattr(assignment.vehicle_id, "vehicle_no", None),
                "summary": {
                    "total": len(stops),
                    "completed": completed,
                    "in_progress": in_progress,
                    "pending": pending,
                    "missed": missed,
                    "completion_percentage": round((completed / len(stops)) * 100, 2),
                },
                "distance_meters": route["distance"],
                "duration_seconds": route["duration"],
                "route_geojson": route["geometry"],
                "vehicle_start": route["vehicle_start"],
                "collection_points": self.get_serializer(stops, many=True).data,
            })

        aggregate["completion_percentage"] = (
            round((aggregate["completed"] / aggregate["total"]) * 100, 2)
            if aggregate["total"]
            else 0
        )
        return Response({"summary": aggregate, "trips": trips})

    @action(detail=False, methods=["post"], url_path="optimize-route")
    def optimize_route(self, request):
        assignment_id = request.data.get("trip_assignment_id")
        if not assignment_id:
            return Response(
                {"trip_assignment_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            raw_vehicle_start = request.data.get("vehicle_start")
            vehicle_start = None
            if isinstance(raw_vehicle_start, (list, tuple)) and len(raw_vehicle_start) == 2:
                try:
                    vehicle_start = [float(raw_vehicle_start[0]), float(raw_vehicle_start[1])]
                except (TypeError, ValueError):
                    return Response(
                        {"vehicle_start": "Use [longitude, latitude]."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            optimized = self._optimize_assignment(assignment_id, vehicle_start)
        except OpenRouteServiceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            "trip_assignment_id": assignment_id,
            "optimized_order": optimized["all_ordered_ids"],
            "remaining_optimized_order": optimized["ordered_ids"],
            "optimized_stop_count": optimized["optimized_stop_count"],
            "completed_stop_count": optimized["completed_stop_count"],
            "vehicle_no": optimized["vehicle_no"],
            "vehicle_start": optimized["vehicle_start"],
            "vehicle_start_source": optimized["vehicle_start_source"],
            "distance_meters": optimized["distance"],
            "duration_seconds": optimized["duration"],
            "route_geojson": optimized["geometry"],
            "route_legs": optimized["route_legs"],
        })

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_collected:
            return Response(
                {"detail": "Collected trip collection points are read-only."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._sync_assignment_and_log(serializer.instance)
        self._optimize_assignment_silently(serializer.instance.trip_assignment_id_id)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._sync_assignment_and_log(serializer.instance)
        self._optimize_assignment_silently(serializer.instance.trip_assignment_id_id)

    def perform_destroy(self, instance):
        assignment_id = instance.trip_assignment_id_id
        previous_data = self._serialize_instance(instance)
        instance.is_deleted = True
        instance.is_active = False
        instance.save(update_fields=["is_deleted", "is_active", "updated_at"])
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )
        self._optimize_assignment_silently(assignment_id)

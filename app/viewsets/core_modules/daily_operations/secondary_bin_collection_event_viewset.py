from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from app.utils.plain_ref import ref_id
from app.models.core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent
from app.models.core_modules.schedule_setup.collection_point import Collection_point
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.waste_masters.bins import Bins
from app.models.masters.waste_masters.wastetype import WasteType
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
from app.serializers.core_modules.daily_operations.secondary_bin_collection_event_serializer import (
    BinCollectionEventSerializer,
)
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.hierarchy import (
    filter_flat_geo_queryset_by_params,
    filter_flat_geo_queryset_by_requester_scope,
)
from app.utils.pagination import LimitOffsetWithPage
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


class BinCollectionEventViewSet(AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "bin_collection_event"
    serializer_class = BinCollectionEventSerializer
    lookup_field = "unique_id"
    permission_resource = "SecondaryBinCollectionEvent"
    # No SearchFilter here — the list's search box matches what the table
    # shows (trip plan, collection point, local body, bin, waste type,
    # vehicle, status, reason), most of which are plain unique_id columns
    # with no DB join. Resolved manually in get_queryset (same pattern as
    # vehicle_breakdown_viewset); adding DRF's SearchFilter on top would AND
    # a narrower condition and hide legitimate matches.
    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["collection_date", "status"]

    AUDIT_MODULE = "transport-masters"
    AUDIT_ENDPOINT = "bin-collection-event"

    def get_queryset(self):
        queryset = (
            BinCollectionEvent.objects
            .filter(is_deleted=False)
        )

        params = self.request.query_params
        trip_assignment = params.get("trip_assignment_id")
        trip_collection_point = params.get("trip_collection_point_id")
        bin_id = params.get("bin_id")
        collection_date = params.get("collection_date") or params.get("date")
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        ward_id = params.get("ward_id") or params.get("ward_ids")

        if trip_assignment:
            queryset = queryset.filter(trip_assignment_id=trip_assignment)
        if trip_collection_point:
            queryset = queryset.filter(trip_collection_point_id=trip_collection_point)
        if bin_id:
            queryset = queryset.filter(bin_id=bin_id)
        if collection_date:
            queryset = queryset.filter(collection_date=collection_date)
        if date_from:
            queryset = queryset.filter(collection_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(collection_date__lte=date_to)
        if ward_id:
            queryset = queryset.filter(ward_id=ward_id)

        # NOTE: trip_assignment_id stores DailyTripAssignment.unique_id
        # while that model's pk is an auto int id, so hops through the
        # assignment (trip plan code, vehicle) go through explicit
        # unique_id subqueries (not PlainRefSearchFilter).
        search = (params.get("search") or params.get("q") or "").strip()
        if search:
            plan_ids = TripPlan.objects.filter(
                Q(display_code__icontains=search) | Q(unique_id__icontains=search)
            ).values("unique_id")
            vehicle_ids = VehicleCreation.objects.filter(
                vehicle_no__icontains=search
            ).values("unique_id")
            assignment_ids = DailyTripAssignment.objects.filter(
                Q(unique_id__icontains=search)
                | Q(trip_plan_id__in=plan_ids)
                | Q(vehicle_id__in=vehicle_ids)
            ).values("unique_id")
            queryset = queryset.filter(
                Q(unique_id__icontains=search)
                | Q(trip_assignment_id__icontains=search)
                | Q(trip_assignment_id__in=assignment_ids)
                | Q(collection_point_id__in=Collection_point.objects.filter(
                    Q(cp_name__icontains=search) | Q(unique_id__icontains=search)
                ).values("unique_id"))
                | Q(bin_id__in=Bins.objects.filter(
                    Q(bin_name__icontains=search) | Q(unique_id__icontains=search)
                ).values("unique_id"))
                | Q(waste_type_id__in=WasteType.objects.filter(
                    waste_type_name__icontains=search
                ).values("unique_id"))
                | Q(vehicle_id__in=vehicle_ids)
                | Q(status__icontains=search)
                | Q(status_reason__icontains=search)
                | Q(ward_id__in=Ward.objects.filter(ward_name__icontains=search).values("unique_id"))
                | Q(state_id__in=State.objects.filter(name__icontains=search).values("unique_id"))
                | Q(district_id__in=District.objects.filter(name__icontains=search).values("unique_id"))
                | Q(area_type_id__in=AreaType.objects.filter(name__icontains=search).values("unique_id"))
                | Q(corporation_id__in=Corporation.objects.filter(corporation_name__icontains=search).values("unique_id"))
                | Q(municipality_id__in=Municipality.objects.filter(municipality_name__icontains=search).values("unique_id"))
                | Q(town_panchayat_id__in=TownPanchayat.objects.filter(town_panchayat_name__icontains=search).values("unique_id"))
                | Q(panchayat_union_id__in=PanchayatUnion.objects.filter(union_name__icontains=search).values("unique_id"))
                | Q(panchayat_id__in=Panchayat.objects.filter(panchayat_name__icontains=search).values("unique_id"))
            )

        # Events carry their own flat geo columns (copied from the assignment
        # on save), so filter on those directly — no join to the assignment.
        queryset = filter_flat_geo_queryset_by_params(queryset, params)
        queryset = filter_flat_geo_queryset_by_requester_scope(queryset, self.request.user)

        return queryset

    # -------------------------------------------------
    # SUMMARY TOTALS — daily/overall collected weight + record count,
    # scoped by the same filters (hierarchy/date/search) as the paginated
    # list, so KPI pills stay correct once the list itself is paginated.
    # -------------------------------------------------

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        today = timezone.localdate()

        overall_weight = queryset.aggregate(total=Sum("collected_weight_kg"))["total"] or 0
        daily_weight = queryset.filter(collection_date=today).aggregate(
            total=Sum("collected_weight_kg")
        )["total"] or 0

        return Response({
            "overall_weight": str(overall_weight),
            "daily_weight": str(daily_weight),
            "count": queryset.count(),
        })

    # -------------------------------------------------
    # DAILY TRIP COLLECTION POINT SYNC
    # -------------------------------------------------

    def _upsert_trip_log_for_assignment(self, assignment):
        """
        Keep admin BinCollectionEvent flow aligned with operator-mobile scans.

        DailyTripLog is created as soon as DailyTripCollectionPoint data exists
        for the trip, then submitted after every collection point is collected.
        """
        if not assignment:
            return

        children = assignment.trip_collection_points.filter(is_deleted=False)
        if not children.exists():
            return

        all_collected = not children.exclude(
            status__in=[
                DailyTripCollectionPoint.STATUS_COLLECTED,
                DailyTripCollectionPoint.STATUS_MISSED,
            ]
        ).exists()
        total_weight = children.aggregate(total=Sum("collected_weight_kg"))["total"] or 0
        vehicle_capacity = getattr(getattr(assignment, "vehicle", None), "capacity", None)
        trip_capacity = getattr(getattr(assignment, "trip_plan", None), "max_vehicle_capacity_kg", None)
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
            trip_assignment_id=ref_id(assignment),
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

    def _apply_event_to_trip_cp(self, trip_cp, event):
        """
        Stamp `trip_cp`'s collected/weight/status fields from `event`'s status,
        without saving or re-syncing the trip log — the caller does that.
        """
        if event.status == BinCollectionEvent.STATUS_NOT_COLLECTED:
            trip_cp.collected_weight_kg = None
            trip_cp.collected_at = None
            trip_cp.is_collected = False
            trip_cp.status = DailyTripCollectionPoint.STATUS_MISSED
        elif event.status == BinCollectionEvent.STATUS_COLLECT_LATER:
            trip_cp.collected_weight_kg = None
            trip_cp.collected_at = None
            trip_cp.is_collected = False
            trip_cp.status = DailyTripCollectionPoint.STATUS_PENDING
        else:
            trip_cp.collected_weight_kg = event.collected_weight_kg or 0
            trip_cp.collected_at = getattr(event, "created_at", None) or timezone.now()
            trip_cp.is_collected = True
            trip_cp.status = DailyTripCollectionPoint.STATUS_COLLECTED

    def _sync_trip_cp_from_event(self, event):
        """
        Sync the linked DailyTripCollectionPoint whenever a BinCollectionEvent is saved.

        Always overwrites weight and marks Collected so the DTCP reflects the latest BCE data.
        Falls back to get_or_create by (assignment, collection_point) if the direct link isn't
        resolved (defensive — trip_collection_point_id is NOT NULL in the model).
        """
        trip_cp = event.trip_collection_point

        if not trip_cp:
            assignment = event.trip_assignment
            collection_point = event.collection_point
            if not assignment or not collection_point:
                return
            trip_cp, _ = DailyTripCollectionPoint.objects.get_or_create(
                trip_assignment_id=ref_id(assignment),
                collection_point_id=ref_id(collection_point),
                defaults={
                    "bin_id": ref_id(getattr(event, "bin_id", None)),
                },
            )

        if not trip_cp:
            return

        self._apply_event_to_trip_cp(trip_cp, event)
        trip_cp.save(update_fields=[
            "collected_weight_kg",
            "collected_at",
            "is_collected",
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "updated_at",
        ])
        assignment = trip_cp.trip_assignment
        assignment.mark_completed_if_all_cps_collected()
        self._upsert_trip_log_for_assignment(assignment)

    def _resync_trip_cp_after_delete(self, deleted_event):
        """
        Called after a BinCollectionEvent is soft-deleted. The linked
        DailyTripCollectionPoint (and downstream DailyTripLog) must not keep
        reflecting the now-deleted event's weight/status — recompute the
        DTCP from whichever non-deleted BinCollectionEvent is now the most
        recent for that stop, or reset it to "not collected" if none remain.
        """
        trip_cp = getattr(deleted_event, "trip_collection_point_id", None)
        if not trip_cp:
            return

        latest_remaining = (
            BinCollectionEvent.objects.filter(
                trip_collection_point_id=ref_id(trip_cp), is_deleted=False
            )
            .order_by("-created_at")
            .first()
        )

        if latest_remaining:
            self._apply_event_to_trip_cp(trip_cp, latest_remaining)
        else:
            trip_cp.collected_weight_kg = None
            trip_cp.collected_at = None
            trip_cp.is_collected = False
            trip_cp.status = DailyTripCollectionPoint.STATUS_PENDING

        trip_cp.save(update_fields=[
            "collected_weight_kg",
            "collected_at",
            "is_collected",
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "updated_at",
        ])
        assignment = trip_cp.trip_assignment
        assignment.mark_completed_if_all_cps_collected()
        self._upsert_trip_log_for_assignment(assignment)

    # -------------------------------------------------
    # CREATE / UPDATE / DELETE
    # -------------------------------------------------

    @transaction.atomic
    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._sync_trip_cp_from_event(serializer.instance)

    @transaction.atomic
    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._sync_trip_cp_from_event(serializer.instance)

    @transaction.atomic
    def perform_destroy(self, instance):
        previous_data = self._serialize_instance(instance)
        instance.is_deleted = True
        instance.is_active = False
        account = self._account_for_request_user()
        update_fields = ["is_deleted", "is_active", "updated_at"]
        if account is not None:
            instance.updated_by = account.pk
            update_fields.append("updated_by")
        instance.save(update_fields=update_fields)
        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=self._serialize_instance(instance),
        )
        self._resync_trip_cp_after_delete(instance)

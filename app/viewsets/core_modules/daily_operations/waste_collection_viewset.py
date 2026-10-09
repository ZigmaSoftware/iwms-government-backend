from django.db import transaction
from django.db.models import Q

from rest_framework import filters, viewsets
from app.utils.plain_ref import ref_id
from app.models.core_modules.daily_operations.waste_collection import WasteCollection
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.serializers.core_modules.daily_operations.waste_collection_serializer import WasteCollectionSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.utils.scoped_viewset import FlatGeoScopedViewSetMixin

class WasteCollectionViewSet(FlatGeoScopedViewSetMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "waste_collection"
    # The "Household collection events" screen in the permission UI.
    permission_resource = "HouseholdCollectionEvent"
    # NOTE: customer/trip-assignment/ward are plain unique_id CharFields now
    # (no DB relation), so no select_related paths exist.
    queryset = WasteCollection.objects.filter(is_deleted=False).order_by("-collection_date","-collection_time")
    serializer_class = WasteCollectionSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    ordering_fields = ["collection_date", "collection_time", "status", "total_quantity"]

    AUDIT_MODULE = "schedule-masters"
    AUDIT_ENDPOINT = "wastecollections"
    # Scoping (params + requester StaffDataScope) is applied automatically by
    # FlatGeoScopedViewSetMixin using the record-level flat geo columns (B2/G2).

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        ward_id = params.get("ward_id") or params.get("ward_ids")
        collection_date = params.get("date") or params.get("collection_date")
        if ward_id:
            queryset = queryset.filter(ward_id=ward_id)
        if collection_date:
            queryset = queryset.filter(collection_date=collection_date)

        # No SearchFilter here — the list's search box matches what the
        # table shows (customer, mobile, trip, vehicle, district, area,
        # location, status), most of which are plain unique_id columns with
        # no DB join. Resolved manually (same pattern as
        # vehicle_breakdown_viewset); adding DRF's SearchFilter on top
        # would AND a narrower condition and hide legitimate matches.
        # NOTE: trip_assignment_id stores DailyTripAssignment.unique_id
        # while that model's pk is an auto int id, so the vehicle hop goes
        # through explicit unique_id subqueries (not PlainRefSearchFilter).
        search = (params.get("search") or params.get("q") or "").strip()
        if search:
            customer_ids = CustomerCreation.objects.filter(
                Q(customer_name__icontains=search)
                | Q(contact_no__icontains=search)
                | Q(unique_id__icontains=search)
            ).values("unique_id")
            vehicle_ids = VehicleCreation.objects.filter(
                vehicle_no__icontains=search
            ).values("unique_id")
            assignment_ids = DailyTripAssignment.objects.filter(
                Q(unique_id__icontains=search) | Q(vehicle_id__in=vehicle_ids)
            ).values("unique_id")
            queryset = queryset.filter(
                Q(unique_id__icontains=search)
                | Q(customer_id__in=customer_ids)
                | Q(trip_assignment_id__icontains=search)
                | Q(trip_assignment_id__in=assignment_ids)
                | Q(status__icontains=search)
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
        return queryset

    @transaction.atomic
    def perform_destroy(self, instance):
        trip_assignment_id = instance.trip_assignment_id
        customer_id = instance.customer_id

        super().perform_destroy(instance)

        if trip_assignment_id is None or customer_id is None:
            return
        self._resync_household_collection_after_delete(trip_assignment_id, customer_id)

    def _resync_household_collection_after_delete(self, trip_assignment_id, customer_id):
        """
        Called after a WasteCollection is soft-deleted. The linked
        DailyTripHouseholdCollection row (and DailyTripLog.household_collected_weight_kg)
        must not keep reflecting the now-deleted collection — recompute the
        household stop from whichever non-deleted WasteCollection is now the
        most recent for that customer+trip, or reset it to "not collected" if
        none remain. Mirrors BinCollectionEventViewSet._resync_trip_cp_after_delete.
        """
        from app.models.core_modules.daily_operations.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog

        dthc = DailyTripHouseholdCollection.objects.filter(
            trip_assignment_id=ref_id(trip_assignment_id),
            customer_id=ref_id(customer_id),
            is_deleted=False,
        ).first()
        if dthc is None:
            return

        latest_remaining = (
            WasteCollection.objects.filter(
                trip_assignment_id=ref_id(trip_assignment_id),
                customer_id=customer_id,
                is_deleted=False,
            )
            .order_by("-collection_date", "-collection_time")
            .first()
        )

        if latest_remaining:
            dthc.mark_collected(latest_remaining)
        else:
            dthc.waste_collection_id = None
            dthc.collected_weight_kg = None
            dthc.collected_at = None
            dthc.is_collected = False
            dthc.status = DailyTripHouseholdCollection.STATUS_PENDING
            dthc.save(update_fields=[
                "waste_collection_id",
                "collected_weight_kg",
                "collected_at",
                "is_collected",
                "status",
                "updated_at",
            ])

        log = DailyTripLog.objects.filter(
            trip_assignment_id=ref_id(trip_assignment_id), is_deleted=False
        ).first()
        if log is None:
            return

        if latest_remaining:
            log.sync_from_household_collections()
        else:
            # sync_from_household_collections() early-returns when no
            # WasteCollection rows remain for this trip, which would leave a
            # stale non-zero total — reset explicitly in that case.
            from decimal import Decimal
            still_has_any = WasteCollection.objects.filter(
                trip_assignment_id=ref_id(trip_assignment_id), is_deleted=False
            ).exists()
            if not still_has_any:
                log.household_collected_weight_kg = Decimal("0")
                DailyTripLog.objects.filter(pk=log.pk).update(
                    household_collected_weight_kg=Decimal("0"),
                )
            else:
                log.sync_from_household_collections()

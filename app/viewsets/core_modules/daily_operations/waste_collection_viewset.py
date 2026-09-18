from django.db import transaction

from rest_framework import filters, viewsets
from app.models.core_modules.daily_operations.waste_collection import WasteCollection
from app.serializers.core_modules.daily_operations.waste_collection_serializer import WasteCollectionSerializer
from app.utils.audit_mixin import AuditViewSetMixin
from app.utils.pagination import LimitOffsetWithPage
from app.utils.scoped_viewset import FlatGeoScopedViewSetMixin

class WasteCollectionViewSet(FlatGeoScopedViewSetMixin, AuditViewSetMixin, viewsets.ModelViewSet):
    throttle_scope = "waste_collection"
    # NOTE: CustomerCreation's own state/district/.../panchayat and this
    # model's record-level geography are plain unique_id CharFields now (no
    # DB relation), so they are no longer valid select_related paths.
    queryset = WasteCollection.objects.filter(is_deleted=False).select_related(
        "customer__property_ref", "customer__sub_property",
    ).order_by("-collection_date","-collection_time")
    serializer_class = WasteCollectionSerializer
    lookup_field = "unique_id"
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = LimitOffsetWithPage
    search_fields = ["unique_id", "customer__customer_name"]
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
            queryset = queryset.filter(ward__unique_id=ward_id)
        if collection_date:
            queryset = queryset.filter(collection_date=collection_date)
        return queryset

    @transaction.atomic
    def perform_destroy(self, instance):
        trip_assignment = instance.trip_assignment_id
        customer = instance.customer

        super().perform_destroy(instance)

        if trip_assignment is None or customer is None:
            return
        self._resync_household_collection_after_delete(trip_assignment, customer)

    def _resync_household_collection_after_delete(self, trip_assignment, customer):
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
            trip_assignment_id=trip_assignment,
            customer_id=customer,
            is_deleted=False,
        ).first()
        if dthc is None:
            return

        latest_remaining = (
            WasteCollection.objects.filter(
                trip_assignment_id=trip_assignment,
                customer=customer,
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
            trip_assignment_id=trip_assignment, is_deleted=False
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
                trip_assignment_id=trip_assignment, is_deleted=False
            ).exists()
            if not still_has_any:
                log.household_collected_weight_kg = Decimal("0")
                DailyTripLog.objects.filter(pk=log.pk).update(
                    household_collected_weight_kg=Decimal("0"),
                )
            else:
                log.sync_from_household_collections()

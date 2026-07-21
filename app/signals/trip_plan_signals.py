from django.db.models.signals import post_save
from django.dispatch import receiver

from app.models.schedule_masters.daily_trip_assignment import DailyTripAssignment
from app.models.schedule_masters.daily_trip_collection_point import (
    DailyTripCollectionPoint,
)
from app.models.schedule_masters.trip_plan_collection_point import (
    TripPlanCollectionPoint,
)
# Most specific level first: a stop/trip plan scoped to a single Panchayat
# should only match customers in that exact Panchayat, not the whole District.
# area_type is a category (urban/rural), not a containment level, so it's
# excluded here - it can't meaningfully narrow a customer match on its own.
_GEO_MATCH_FIELDS = (
    "panchayat",
    "panchayat_union",
    "town_panchayat",
    "municipality",
    "corporation",
    "district",
    "state",
)


def _geo_filter_for(obj):
    """The exact (field, value) filter matching CustomerCreation rows scoped
    to precisely `obj`'s most specific populated geo field (e.g. a stop
    scoped to a Panchayat only matches customers whose `panchayat` FK
    equals that panchayat) - not its ancestors/descendants. Returns None if
    `obj` has no geo field populated."""
    if not obj:
        return None
    for field in _GEO_MATCH_FIELDS:
        value = getattr(obj, f"{field}_id", None)
        if value:
            return f"{field}_id", value
    return None


def _customers_for_household_stop(stop):
    from app.models.masters.customer_masters.customercreation import CustomerCreation

    is_bulk_stop = stop.collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BULK
    if stop.customer_id_id:
        return CustomerCreation.objects.filter(
            unique_id=stop.customer_id_id,
            is_deleted=False,
            is_bulkwaste_generator=is_bulk_stop,
        )

    geo_filter = _geo_filter_for(stop) or _geo_filter_for(stop.trip_plan_id)
    if not geo_filter:
        return CustomerCreation.objects.none()

    field, value = geo_filter
    return CustomerCreation.objects.filter(
        is_deleted=False,
        is_active=True,
        is_bulkwaste_generator=is_bulk_stop,
        **{field: value},
    )


def _create_daily_household_collections(assignment, stop):
    from app.models.schedule_masters.daily_trip_household_collection import (
        DailyTripHouseholdCollection,
    )

    collection_type = (
        DailyTripHouseholdCollection.COLLECTION_TYPE_BULK
        if stop.collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BULK
        else DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD
    )
    created_count = 0
    for offset, customer in enumerate(_customers_for_household_stop(stop), start=0):
        _, created = DailyTripHouseholdCollection.objects.get_or_create(
            trip_assignment_id=assignment,
            customer_id=customer,
            collection_type=collection_type,
            defaults={
                "sequence": stop.sequence + offset,
                "is_collected": False,
                "status": DailyTripHouseholdCollection.STATUS_PENDING,
            },
        )
        if created:
            created_count += 1
    return created_count


def sync_daily_assignment_stops_from_plan(assignment):
    """Clone the assignment's Trip Plan stops into its daily child tables.

    Uses get_or_create throughout, so it is safe to call repeatedly: it only
    ADDS stops that aren't cloned yet (e.g. household stops added to the plan
    after the assignment was first created) and never deletes or overwrites an
    existing daily stop or its collected data. Returns the number of new rows.
    """
    if not assignment.trip_plan_id_id:
        return 0

    plan_stops = TripPlanCollectionPoint.objects.filter(
        trip_plan_id=assignment.trip_plan_id,
        collection_type=assignment.trip_plan_id.collection_type,
        is_active=True,
        is_deleted=False,
    ).order_by("sequence")

    added = 0
    for stop in plan_stops:
        if stop.collection_type == TripPlanCollectionPoint.COLLECTION_TYPE_BIN:
            if not stop.collection_point_id_id:
                continue
            _, created = DailyTripCollectionPoint.objects.get_or_create(
                trip_assignment_id=assignment,
                collection_point_id=stop.collection_point_id,
                defaults={
                    "bin_id": stop.bin_id,
                    "sequence": stop.sequence,
                    "is_collected": False,
                    "status": DailyTripCollectionPoint.STATUS_PENDING,
                    "created_by": getattr(assignment, "created_by", None),
                },
            )
            if created:
                added += 1

        elif stop.collection_type in {
            TripPlanCollectionPoint.COLLECTION_TYPE_HOUSEHOLD,
            TripPlanCollectionPoint.COLLECTION_TYPE_BULK,
        }:
            added += _create_daily_household_collections(assignment, stop)

    return added


@receiver(post_save, sender=DailyTripAssignment)
def copy_trip_plan_stops_to_daily_assignment(sender, instance, created, **kwargs):
    if not created:
        return
    sync_daily_assignment_stops_from_plan(instance)


def _describe_waste_collection(instance):
    """Compact, customer-facing summary naming waste type(s) and weight."""
    breakdown = [
        (label, value)
        for label, value in (
            ("wet", instance.wet_waste),
            ("dry", instance.dry_waste),
            ("mixed", instance.mixed_waste),
        )
        if value
    ]
    if not breakdown:
        return "Your waste was just collected. Thank you!"
    if len(breakdown) == 1:
        label, value = breakdown[0]
        return f"{value:g} kg of {label} waste collected. Thank you!"
    parts = ", ".join(f"{value:g} kg {label}" for label, value in breakdown)
    return f"{instance.total_quantity:g} kg collected ({parts}). Thank you!"


@receiver(post_save, sender="app.WasteCollection")
def sync_household_collection_on_waste_save(sender, instance, **kwargs):
    """When a WasteCollection is saved with a trip_assignment_id:
    1. Find or create the DailyTripHouseholdCollection entry for that customer + trip.
    2. Mark it collected with the recorded weight.
    3. Find or create the DailyTripLog for the trip.
    4. Sync household_collected_weight_kg on the log.
    5. Auto-submit the log once all household stops are collected.
    """
    if not instance.trip_assignment_id_id or instance.is_deleted:
        return

    from app.models.schedule_masters.daily_trip_household_collection import (
        DailyTripHouseholdCollection,
    )
    from app.models.schedule_masters.daily_trip_log import DailyTripLog

    collection_type = (
        DailyTripHouseholdCollection.COLLECTION_TYPE_BULK
        if getattr(instance.customer, "is_bulkwaste_generator", False)
        else DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD
    )
    # 1. Update / create the household collection entry
    dthc, _ = DailyTripHouseholdCollection.objects.get_or_create(
        trip_assignment_id=instance.trip_assignment_id,
        customer_id=instance.customer,
        collection_type=collection_type,
        defaults={"status": DailyTripHouseholdCollection.STATUS_PENDING},
    )
    dthc.mark_collected(instance)

    # Notify the customer instantly that their waste was collected. Safe
    # no-op if push isn't configured or they have no registered device.
    from app.services.push_notification_service import send_push_to_customer
    send_push_to_customer(
        instance.customer,
        "Waste collected",
        _describe_waste_collection(instance),
        data={
            "event": "household_collected",
            "trip_assignment_id": str(instance.trip_assignment_id_id),
            "wet_waste": instance.wet_waste,
            "dry_waste": instance.dry_waste,
            "mixed_waste": instance.mixed_waste,
            "total_quantity": instance.total_quantity,
        },
    )

    # 2. Find or auto-create the trip log
    log = DailyTripLog.objects.filter(
        trip_assignment_id=instance.trip_assignment_id_id,
        is_deleted=False,
    ).first()

    if log is None:
        try:
            log = DailyTripLog(
                trip_assignment_id=instance.trip_assignment_id,
                log_status=DailyTripLog.LOG_STATUS_DRAFT,
                remarks="Auto-generated from household waste collections.",
            )
            # autofill_from_assignment() is called inside save()
            log.save()
        except Exception:
            # If assignment is missing required fields (no staff template,
            # vehicle, etc.) skip log creation gracefully.
            return

    # 3. Sync household weight onto the log
    log.sync_from_household_collections()

    # 4. Auto-submit when ALL household stops for this trip are collected
    #    (mirrors DailyTripCollectionPointViewSet auto-submit for bins)
    log.refresh_from_db(fields=["log_status", "household_collected_weight_kg"])
    if log.log_status != DailyTripLog.LOG_STATUS_DRAFT:
        return  # already submitted / verified — don't touch

    hh_weight = log.household_collected_weight_kg or 0
    if hh_weight <= 0:
        return

    all_hh = DailyTripHouseholdCollection.objects.filter(
        trip_assignment_id=instance.trip_assignment_id,
        is_deleted=False,
    )
    if all_hh.exists() and not all_hh.filter(is_collected=False).exists():
        DailyTripLog.objects.filter(pk=log.pk).update(
            log_status=DailyTripLog.LOG_STATUS_SUBMITTED,
        )


@receiver(post_save, sender="app.BinCollectionEvent")
def sync_trip_log_on_bin_event_save(sender, instance, **kwargs):
    """Keep the trip's DailyTripLog in sync on EVERY bin scan, not only when the
    whole trip is completed (mirrors sync_household_collection_on_waste_save):
    1. Find or auto-create the DailyTripLog (Draft) for the trip.
    2. Sync collected_weight_kg from the trip's BinCollectionEvent records.
    3. Auto-submit once all bin collection points are resolved (Collected/Missed).

    Without this, a partially-collected trip never gets a log row — the mobile
    scan flow only wrote one when progress was 100% complete.
    """
    if not instance.trip_assignment_id_id or instance.is_deleted:
        return

    from app.models.schedule_masters.daily_trip_log import DailyTripLog

    log = DailyTripLog.objects.filter(
        trip_assignment_id=instance.trip_assignment_id_id,
        is_deleted=False,
    ).first()

    if log is None:
        try:
            log = DailyTripLog(
                trip_assignment_id=instance.trip_assignment_id,
                log_status=DailyTripLog.LOG_STATUS_DRAFT,
                remarks="Auto-generated from bin collection scans.",
            )
            # autofill_from_assignment() runs inside save(); save() also calls
            # sync_from_bin_collection_events() so weight is populated on create.
            log.save()
        except Exception:
            # Assignment missing required fields (staff template, vehicle, ...)
            # — skip log creation gracefully, exactly like the household path.
            return
    else:
        # Existing (Draft) log from an earlier scan — refresh its bin weight.
        log.sync_from_secondary_bin_collection_events()

    # Auto-submit when ALL bin collection points for this trip are resolved.
    log.refresh_from_db(fields=["log_status", "collected_weight_kg"])
    if log.log_status != DailyTripLog.LOG_STATUS_DRAFT:
        return  # already submitted / verified — don't touch
    if (log.collected_weight_kg or 0) <= 0:
        return

    cps = DailyTripCollectionPoint.objects.filter(
        trip_assignment_id=instance.trip_assignment_id,
        is_deleted=False,
    )
    unresolved = cps.exclude(
        status__in=[
            DailyTripCollectionPoint.STATUS_COLLECTED,
            DailyTripCollectionPoint.STATUS_MISSED,
        ]
    )
    if cps.exists() and not unresolved.exists():
        DailyTripLog.objects.filter(pk=log.pk).update(
            log_status=DailyTripLog.LOG_STATUS_SUBMITTED,
        )

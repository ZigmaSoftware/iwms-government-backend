from decimal import Decimal

from django.db.models import Sum

HOUSEHOLD_WASTE_TYPE_NAMES = {
    "wet_waste": "Wet Waste",
    "dry_waste": "Dry Waste",
    "mixed_waste": "Mixed Waste",
    "sanitary_waste": "Sanitary Waste",
}

# Sentinel waste_type_id used for household-sourced rows that don't have a
# matching WasteType master record by name. Keeps the "id" key populated
# (reports index/display by it) without colliding with real WasteType ids.
HOUSEHOLD_WASTE_TYPE_FALLBACK_ID_PREFIX = "HOUSEHOLD"


def waste_type_breakdown_for_assignment(assignment):
    """Actual weight collected per waste type for one DailyTripAssignment,
    combining secondary/bin collection events (each carries its own waste
    type + weight) and household collections (wet/dry/mixed columns, mapped
    to WasteType master names)."""
    from app.models.masters.waste_masters.wastetype import WasteType
    from app.models.core_modules.daily_operations.waste_collection import WasteCollection
    from app.models.core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent

    totals = {}

    bin_rows = (
        BinCollectionEvent.objects.filter(trip_assignment_id=assignment, is_deleted=False)
        .values("waste_type_id", "waste_type_id__waste_type_name")
        .annotate(total_weight=Sum("collected_weight_kg"))
    )
    for row in bin_rows:
        name = row["waste_type_id__waste_type_name"]
        if not name or not row["total_weight"]:
            continue
        totals[name] = totals.get(name, Decimal("0")) + row["total_weight"]

    household_rows = WasteCollection.objects.filter(
        trip_assignment_id=assignment, is_deleted=False
    ).aggregate(
        wet_waste=Sum("wet_waste"),
        dry_waste=Sum("dry_waste"),
        mixed_waste=Sum("mixed_waste"),
        sanitary_waste=Sum("sanitary_waste"),
    )
    waste_type_names = set(
        WasteType.objects.filter(is_deleted=False).values_list("waste_type_name", flat=True)
    )
    for column, label in HOUSEHOLD_WASTE_TYPE_NAMES.items():
        value = household_rows.get(column)
        if not value:
            continue
        name = label if label in waste_type_names else label
        totals[name] = totals.get(name, Decimal("0")) + Decimal(str(value))

    return [
        {"waste_type_name": name, "collected_weight_kg": totals[name]}
        for name in totals
    ]


def _household_name_to_waste_type(waste_type_by_name):
    """Map each HOUSEHOLD_WASTE_TYPE_NAMES label to a (id, name) pair.

    Falls back to a synthetic id (prefixed so it never collides with a real
    WasteType.unique_id) plus the raw label as display name when no WasteType
    master row exists with that name — per product decision, never drop the
    data or crash.
    """
    resolved = {}
    for column, label in HOUSEHOLD_WASTE_TYPE_NAMES.items():
        wt = waste_type_by_name.get(label)
        if wt is not None:
            resolved[column] = (wt.unique_id, wt.waste_type_name)
        else:
            resolved[column] = (f"{HOUSEHOLD_WASTE_TYPE_FALLBACK_ID_PREFIX}-{column}", label)
    return resolved


def bulk_waste_type_rows_for_trip_assignments(
    trip_assignment_ids,
    source="bin",
    extra_group_by=(),
):
    """Per-(trip_assignment_id, waste_type) weight rows for a bulk set of trip
    assignments, computed as a small, fixed number of aggregated queries
    (never one query per DailyTripLog row) so bulk reports stay efficient
    across hundreds/thousands of trips.

    Mirrors waste_type_breakdown_for_assignment(), but:
      - operates on many trip_assignment_ids at once via GROUP BY, instead of
        looping per-assignment in Python, and
      - accepts extra_group_by (e.g. ("trip_date",) or ("district_id",
        "district__name")) so callers can fold report-specific grouping
        columns (that live on DailyTripLog, not on BinCollectionEvent /
        WasteCollection) directly into the same aggregation pass by joining
        back through DailyTripLog.

    source: "bin" -> only BinCollectionEvent-backed weight
            "household" -> only WasteCollection-backed weight (mapped by name)
            "all" -> both, merged per waste type

    Returns a list of dicts, one per (trip_assignment_id, *extra_group_by,
    waste_type_id) combination that has nonzero weight:
        {
            "trip_assignment_id": ...,
            <extra_group_by fields...>,
            "waste_type_id": ...,
            "waste_type_name": ...,
            "weight_kg": Decimal,
        }
    Callers join this back to their DailyTripLog rows (by trip_assignment_id,
    plus matching extra_group_by values) to build per-waste-type report rows,
    while still computing trip counts / overall totals directly from the base
    DailyTripLog queryset (a trip must never be double-counted in "total
    trips" just because it spans multiple waste types).
    """
    from app.models.masters.waste_masters.wastetype import WasteType
    from app.models.core_modules.daily_operations.waste_collection import WasteCollection
    from app.models.core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent

    trip_assignment_ids = list(trip_assignment_ids)
    rows_by_key = {}

    def _add(key_tuple, extra_values, waste_type_id, waste_type_name, weight):
        if not weight:
            return
        full_key = key_tuple + (waste_type_id,)
        existing = rows_by_key.get(full_key)
        if existing is None:
            rows_by_key[full_key] = {
                "trip_assignment_id": key_tuple[0],
                **dict(zip(extra_group_by, extra_values)),
                "waste_type_id": waste_type_id,
                "waste_type_name": waste_type_name,
                "weight_kg": Decimal(str(weight)),
            }
        else:
            existing["weight_kg"] += Decimal(str(weight))

    if not trip_assignment_ids:
        return []

    if source in ("bin", "all"):
        bin_group_fields = [
            "trip_assignment_id",
            *(f"trip_assignment_id__daily_trip_log__{f}" for f in extra_group_by),
            "waste_type_id",
            "waste_type_id__waste_type_name",
        ]
        bin_rows = (
            BinCollectionEvent.objects.filter(
                trip_assignment_id__in=trip_assignment_ids, is_deleted=False
            )
            .values(*bin_group_fields)
            .annotate(total_weight=Sum("collected_weight_kg"))
        )
        for row in bin_rows:
            extra_values = tuple(
                row[f"trip_assignment_id__daily_trip_log__{f}"] for f in extra_group_by
            )
            key_tuple = (row["trip_assignment_id"],) + extra_values
            _add(
                key_tuple,
                extra_values,
                row["waste_type_id"],
                row["waste_type_id__waste_type_name"] or row["waste_type_id"],
                row["total_weight"],
            )

    if source in ("household", "all"):
        household_group_fields = [
            "trip_assignment_id",
            *(f"trip_assignment_id__daily_trip_log__{f}" for f in extra_group_by),
        ]
        household_rows = (
            WasteCollection.objects.filter(
                trip_assignment_id__in=trip_assignment_ids, is_deleted=False
            )
            .values(*household_group_fields)
            .annotate(
                wet_waste=Sum("wet_waste"),
                dry_waste=Sum("dry_waste"),
                mixed_waste=Sum("mixed_waste"),
            )
        )
        waste_type_by_name = {
            wt.waste_type_name: wt
            for wt in WasteType.objects.filter(is_deleted=False)
        }
        household_map = _household_name_to_waste_type(waste_type_by_name)

        for row in household_rows:
            extra_values = tuple(
                row[f"trip_assignment_id__daily_trip_log__{f}"] for f in extra_group_by
            )
            key_tuple = (row["trip_assignment_id"],) + extra_values
            for column in HOUSEHOLD_WASTE_TYPE_NAMES:
                value = row.get(column)
                if not value:
                    continue
                wt_id, wt_name = household_map[column]
                _add(key_tuple, extra_values, wt_id, wt_name, value)

    return list(rows_by_key.values())

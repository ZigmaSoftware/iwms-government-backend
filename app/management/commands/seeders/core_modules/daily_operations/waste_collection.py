from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.core_modules.daily_operations.waste_collection import WasteCollection
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.schedule_setup.trip_plan import TripPlan

TARGET = 15

# (wet, dry, mixed) kg presets — cycled through for varied, reproducible data
WASTE_PRESETS = [
    (3.5, 1.2, 0.0),
    (2.0, 2.5, 0.5),
    (5.0, 0.0, 1.0),
    (1.5, 1.5, 0.0),
    (4.2, 3.1, 0.8),
    (0.0, 2.0, 3.0),
    (6.0, 1.0, 0.0),
    (2.8, 2.8, 1.4),
]

GEO_FIELDS = (
    "panchayat",
    "panchayat_union",
    "town_panchayat",
    "municipality",
    "corporation",
    "district",
    "state",
)


class WasteCollectionSeeder(BaseSeeder):
    """Seed household waste-collection records, one per existing customer
    (household), skipping any household that already has a record so re-runs
    stay idempotent."""

    name = "waste_collection"

    def run(self):
        customers = list(
            CustomerCreation.objects.filter(is_deleted=False)
            .order_by("customer_name")
        )

        if not customers:
            self.log("No CustomerCreation (household) records found — aborting.")
            return

        # Waste collections belong only to household trips. Bulk/bin assignments
        # must not receive an individual-house collection event.
        trip_assignments = list(
            DailyTripAssignment.objects.filter(
                is_deleted=False,
                trip_plan_id__collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD,
            ).order_by("-trip_date", "scheduled_time", "unique_id")
        )

        created_count = 0
        for index, customer in enumerate(customers):
            if created_count >= TARGET:
                break

            if WasteCollection.objects.filter(
                customer=customer, is_deleted=False
            ).exists():
                continue

            wet, dry, mixed = WASTE_PRESETS[created_count % len(WASTE_PRESETS)]
            trip_assignment = self._matching_assignment(customer, trip_assignments)

            WasteCollection.objects.create(
                customer=customer,
                trip_assignment_id=trip_assignment,
                collection_date=(
                    trip_assignment.trip_date
                    if trip_assignment
                    else timezone.localdate()
                ),
                wet_waste=wet,
                dry_waste=dry,
                mixed_waste=mixed,
                # total_quantity is auto-calculated in WasteCollection.save()
            )
            created_count += 1

        self.log(f"---WasteCollection seeded | created={created_count}---")

    @staticmethod
    def _matching_assignment(customer, assignments):
        """Return a household assignment scoped to the customer's local body.

        Match the most-specific populated geography so a collection never gets
        attached to an unrelated scheduled route. The assignment list is newest
        first, making the selected trip deterministic.
        """
        for field in GEO_FIELDS:
            customer_geo_id = getattr(customer, f"{field}_id", None)
            if customer_geo_id:
                return next(
                    (
                        assignment
                        for assignment in assignments
                        if getattr(assignment, f"{field}_id", None) == customer_geo_id
                    ),
                    None,
                )
        return None

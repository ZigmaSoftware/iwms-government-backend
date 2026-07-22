from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.core_modules.daily_operations.waste_collection import WasteCollection
from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment

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

        # Optional: spread a few available trip assignments across the records
        trip_assignments = list(
            DailyTripAssignment.objects.filter(is_deleted=False).order_by("unique_id")
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
            trip_assignment = (
                trip_assignments[created_count % len(trip_assignments)]
                if trip_assignments
                else None
            )

            WasteCollection.objects.create(
                customer=customer,
                trip_assignment_id=trip_assignment,
                wet_waste=wet,
                dry_waste=dry,
                mixed_waste=mixed,
                # total_quantity is auto-calculated in WasteCollection.save()
            )
            created_count += 1

        self.log(f"---WasteCollection seeded | created={created_count}---")

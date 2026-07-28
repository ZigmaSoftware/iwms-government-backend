from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation


class VehicleTypeCreationSeeder(BaseSeeder):
    name = "VehicleTypeCreationSeeder"

    # (vehicleType, description)
    VEHICLE_TYPES = [
        ("Compactor Truck", "Heavy compactor for municipal waste collection"),
        ("Tipper Truck",    "Open tipper for bulk and dry waste transport"),
        ("Mini Truck",      "Small truck for narrow road access"),
        ("Auto Rickshaw",   "Three-wheeler for small quantity collection"),
        ("Tricycle",        "Manual pedal tricycle for short-range collection"),
    ]

    def run(self):
        for vehicle_type, description in self.VEHICLE_TYPES:
            obj, created = VehicleTypeCreation.objects.get_or_create(
                vehicleType=vehicle_type,
                defaults={"description": description, "is_active": True, "is_deleted": False},
            )
            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.is_active = True
                obj.save(update_fields=["is_deleted", "is_active"])

        self.log(f"---Vehicle types seeded ({len(self.VEHICLE_TYPES)} records)---")

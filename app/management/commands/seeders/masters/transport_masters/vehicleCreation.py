from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.transport_masters.fuel import Fuel
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation


class VehicleCreationSeeder(BaseSeeder):
    name = "VehicleCreationSeeder"

    # (vehicle_no, vehicle_type, fuel_type, capacity_kg, condition)
    VEHICLES = [
        ("TN01AB1234", "Compactor Truck", "Diesel",   5000, "NEW"),
        ("TN01AB5678", "Tipper Truck",    "Diesel",   4000, "NEW"),
        ("TN02CD1111", "Mini Truck",      "Petrol",   1500, "NEW"),
        ("TN02CD2222", "Auto Rickshaw",   "CNG",       300, "NEW"),
        ("TN03EF3333", "Tricycle",        "Electric",  100, "NEW"),
    ]

    def run(self):
        count = 0
        for vehicle_no, vtype_name, fuel_name, capacity, condition in self.VEHICLES:
            vehicle_type = VehicleTypeCreation.objects.filter(vehicleType=vtype_name).first()
            fuel_type = Fuel.objects.filter(fuel_type=fuel_name).first()

            if not vehicle_type:
                self.log(f"VehicleType '{vtype_name}' not found — skipping {vehicle_no}.")
                continue
            if not fuel_type:
                self.log(f"Fuel '{fuel_name}' not found — skipping {vehicle_no}.")
                continue

            _, created = VehicleCreation.objects.get_or_create(
                vehicle_no=vehicle_no,
                defaults={
                    "vehicle_type": vehicle_type,
                    "fuel_type": fuel_type,
                    "capacity": capacity,
                    "vehicle_condition": condition,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                count += 1

        self.log(f"---Vehicles seeded ({count} created)---")

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from app.management.commands.seeders.base import BaseSeeder
from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.management.commands.seeders.ward_utils import geo_defaults_for_local_body, local_bodies_for_district
from app.models.masters.transport_masters.fuel import Fuel
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation

SLOTS_PER_WARD = 2  # one vehicle for the ward's bin route, one for its household route
# One spare vehicle per local body, beyond what TripPlanSeeder's ward slots
# consume — otherwise every vehicle is claimed 1:1 by a ward-level trip plan
# and driver_user.py (which picks an existing, unclaimed vehicle rather than
# creating its own) has nothing left to pick.
SPARE_PER_LOCAL_BODY = 1

# (vehicle_type, fuel_type, capacity_kg, mileage_kmpl, tank_capacity_l)
VEHICLE_SPECS = [
    ("Compactor Truck", "Diesel", 5500, Decimal("3.5"), Decimal("120")),
    ("Tipper Truck", "Diesel", 4000, Decimal("4.5"), Decimal("100")),
    ("Mini Truck", "Petrol", 1500, Decimal("9.0"), Decimal("45")),
    ("Auto Rickshaw", "CNG", 300, Decimal("18.0"), Decimal("15")),
    ("Tricycle", "Electric", 100, Decimal("0"), Decimal("0")),
    ("Compactor Truck", "Diesel", 6000, Decimal("3.2"), Decimal("140")),
]
SERIES_LETTERS = ["AB", "CD", "EF", "GH", "JK", "LM", "NP", "QR", "ST", "UV", "WX", "YZ"]


class VehicleCreationSeeder(BaseSeeder):
    """One vehicle per (local body, ward, collection-type) slot: every local
    body (Corporation, Municipality, Town Panchayat, Panchayat Union, each
    Panchayat) owns a fleet sized to exactly its own ward_count x 2 — never
    shared with another local body's trip plans. Fully geo-scoped to the
    owning local body plus full detail-field coverage (mileage, insurance,
    fuel tank capacity, service record — previously all left null)."""

    name = "VehicleCreationSeeder"

    def run(self):
        count = 0
        for district_name, geo in DISTRICTS.items():
            prefix = geo["vehicle_prefix"]
            local_bodies = local_bodies_for_district(district_name)
            vehicle_idx = 0

            for lb in local_bodies:
                geo_defaults = geo_defaults_for_local_body(lb["parent_type"], lb["parent"], include_country=True)
                slots = lb["ward_count"] * SLOTS_PER_WARD + SPARE_PER_LOCAL_BODY
                for _slot in range(slots):
                    spec_idx = vehicle_idx % len(VEHICLE_SPECS)
                    vtype_name, fuel_name, capacity, mileage, tank = VEHICLE_SPECS[spec_idx]
                    vehicle_type = VehicleTypeCreation.objects.filter(vehicleType=vtype_name).first()
                    fuel_type = Fuel.objects.filter(fuel_type=fuel_name).first()
                    if not vehicle_type or not fuel_type:
                        vehicle_idx += 1
                        continue

                    series = SERIES_LETTERS[vehicle_idx % len(SERIES_LETTERS)]
                    vehicle_no = f"{prefix}{series}{1001 + vehicle_idx:04d}"
                    insurance_expiry = timezone.localdate() + timedelta(days=180 + (vehicle_idx % 180))

                    _, created = VehicleCreation.objects.get_or_create(
                        vehicle_no=vehicle_no,
                        defaults={
                            **geo_defaults,
                            "vehicle_type": vehicle_type,
                            "fuel_type": fuel_type,
                            "capacity": capacity,
                            "mileage_per_liter": mileage,
                            "service_record": (
                                f"Last serviced at district workshop; routine maintenance "
                                f"up to date as of {timezone.localdate().isoformat()}."
                            ),
                            "vehicle_insurance": f"INS-{geo['code']}-{1001 + vehicle_idx:05d}",
                            "insurance_expiry_date": insurance_expiry,
                            "vehicle_condition": "NEW",
                            "fuel_tank_capacity": tank,
                            "is_active": True,
                            "is_deleted": False,
                        },
                    )
                    if created:
                        count += 1
                    vehicle_idx += 1

        self.log(f"---Vehicles seeded ({count} created)---")

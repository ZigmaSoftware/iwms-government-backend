from app.management.commands.seeders.base import BaseSeeder
from app.models.transport_masters.fuel import Fuel


class FuelSeeder(BaseSeeder):
    name = "fuel"

    # (fuel_type, description)
    FUELS = [
        ("Diesel",    "High-efficiency fuel for heavy vehicles"),
        ("Petrol",    "Petroleum-based fuel for light vehicles"),
        ("CNG",       "Compressed Natural Gas"),
        ("Electric",  "Battery-powered electric vehicles"),
        ("LPG",       "Liquefied Petroleum Gas"),
    ]

    def run(self):
        for fuel_type, description in self.FUELS:
            obj, created = Fuel.objects.get_or_create(
                fuel_type=fuel_type,
                defaults={"description": description, "is_active": True, "is_deleted": False},
            )
            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.is_active = True
                obj.save(update_fields=["is_deleted", "is_active"])

        self.log(f"---Fuel types seeded ({len(self.FUELS)} records)---")

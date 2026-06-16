# core/management/commands/seeders/assets/fuel.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.transport_masters.fuel import Fuel


class FuelSeeder(BaseSeeder):
    name = "fuel"

    # (fuel_type, description)
    FUELS = [
        ("Petrol",               "Petroleum-based fuel for light vehicles"),
        ("Diesel",               "High-efficiency fuel for heavy vehicles"),
        ("CNG",                  "Compressed Natural Gas"),
        ("Electric",             "Battery-powered electric vehicles"),
        ("Hydrogen",             "Hydrogen fuel cell vehicles"),
        ("LPG",                  "Liquefied Petroleum Gas"),
        ("Ethanol",              "Bio-ethanol blended fuel"),
        ("Solar",                "Solar-assisted electric vehicles"),
        ("Hybrid Petrol-EV",     "Petrol and electric hybrid"),
        ("Hybrid Diesel-EV",     "Diesel and electric hybrid"),
        ("Biodiesel",            "Biodiesel from renewable sources"),
        ("Methanol",             "Methanol-based fuel"),
        ("Natural Gas",          "Uncompressed natural gas"),
        ("Propane",              "Propane (LPG variant) fuel"),
        ("Biogas",               "Biogas from organic waste"),
    ]

    def run(self):
        for fuel_type, description in self.FUELS:
            obj, created = Fuel.objects.get_or_create(
                fuel_type=fuel_type,
                defaults={
                    "description": description,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.is_active = True
                obj.save(update_fields=["is_deleted", "is_active"])

        self.log(f"---Fuel types seeded ({len(self.FUELS)} records)---")

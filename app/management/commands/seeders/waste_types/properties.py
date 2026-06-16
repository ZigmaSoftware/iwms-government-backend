# core/management/commands/seeders/assets/property.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.waste_types.property import Property


class PropertySeeder(BaseSeeder):
    name = "property"

    PROPERTIES = [
        "Residential",
        "Commercial",
        "Industrial",
        "Institutional",
        "Agricultural",
        "Educational",
        "Healthcare",
        "Hospitality",
        "Retail",
        "Office",
        "Mixed Use",
        "Government",
        "Religious",
        "Recreational",
        "Transportation",
    ]

    def run(self):
        for prop in self.PROPERTIES:
            obj, created = Property.objects.get_or_create(
                property_name=prop,
                defaults={
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.is_active = True
                obj.save(update_fields=["is_deleted", "is_active"])

        self.log(f"---Properties seeded ({len(self.PROPERTIES)} records)---")

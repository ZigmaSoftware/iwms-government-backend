from app.management.commands.seeders.base import BaseSeeder
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class SubPropertySeeder(BaseSeeder):
    name = "sub_property"

    # property_name → sub_property_name (one each, total = 5)
    PROPERTY_MAP = {
        "Residential":   "Apartment",
        "Commercial":    "Shop",
        "Industrial":    "Factory",
        "Institutional": "School",
        "Government":    "Municipal Office",
    }

    def run(self):
        total = 0
        for property_name, sub_name in self.PROPERTY_MAP.items():
            property_obj = Property.objects.filter(
                property_name=property_name, is_deleted=False
            ).first()
            if not property_obj:
                self.log(f"Property '{property_name}' not found — skipping.")
                continue

            obj, created = SubProperty.objects.get_or_create(
                property_id=property_obj,
                sub_property_name=sub_name,
                defaults={"is_active": True, "is_deleted": False},
            )
            if not created and obj.is_deleted:
                obj.is_deleted = False
                obj.is_active = True
                obj.save(update_fields=["is_deleted", "is_active"])
            total += 1

        self.log(f"---Sub-properties seeded ({total} records)---")

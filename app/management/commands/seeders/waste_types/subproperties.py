# core/management/commands/seeders/assets/subproperty.py
from app.management.commands.seeders.base import BaseSeeder
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class SubPropertySeeder(BaseSeeder):
    name = "sub_property"

    # property_name → list of sub_property names (total = 15)
    PROPERTY_MAP = {
        "Residential":   ["Apartment", "Individual House", "Villa", "Townhouse"],
        "Commercial":    ["Office", "Shop", "Mall", "Restaurant"],
        "Industrial":    ["Factory", "Warehouse"],
        "Institutional": ["Hospital", "School"],
        "Agricultural":  ["Farm", "Plantation"],
        "Government":    ["Municipal Office"],
    }

    def run(self):
        total = 0
        for property_name, subproperties in self.PROPERTY_MAP.items():
            property_obj = Property.objects.filter(
                property_name=property_name, is_deleted=False
            ).first()
            if not property_obj:
                self.log(f"Property '{property_name}' not found — skipping.")
                continue

            for sub_name in subproperties:
                obj, created = SubProperty.objects.get_or_create(
                    property_id=property_obj,
                    sub_property_name=sub_name,
                    defaults={
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                if not created and obj.is_deleted:
                    obj.is_deleted = False
                    obj.is_active = True
                    obj.save(update_fields=["is_deleted", "is_active"])
                total += 1

        self.log(f"---Sub-properties seeded ({total} records)---")

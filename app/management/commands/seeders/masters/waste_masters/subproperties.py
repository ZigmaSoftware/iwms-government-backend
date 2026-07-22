from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty


class SubPropertySeeder(BaseSeeder):
    name = "sub_property"

    # property_name → sub-property names. Residential needs both supported
    # household shapes; customer demo rows intentionally use Individual House.
    PROPERTY_MAP = {
        "Residential":   ("Individual House", "Apartment"),
        "Commercial":    ("Shop",),
        "Industrial":    ("Factory",),
        "Institutional": ("School",),
        "Government":    ("Municipal Office",),
    }

    def run(self):
        total = 0
        for property_name, sub_names in self.PROPERTY_MAP.items():
            property_obj = Property.objects.filter(
                property_name=property_name, is_deleted=False
            ).first()
            if not property_obj:
                self.log(f"Property '{property_name}' not found — skipping.")
                continue

            for sub_name in sub_names:
                obj, created = SubProperty.objects.get_or_create(
                    property_id=property_obj,
                    sub_property_name=sub_name,
                    defaults={"is_active": True, "is_deleted": False},
                )
                if not created and (obj.is_deleted or not obj.is_active):
                    obj.is_deleted = False
                    obj.is_active = True
                    obj.save(update_fields=["is_deleted", "is_active"])
                total += 1

        self.log(f"---Sub-properties seeded ({total} records)---")

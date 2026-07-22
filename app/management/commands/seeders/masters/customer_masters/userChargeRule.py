from decimal import Decimal

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.customer_masters.userchargerule import UserChargeRule
from app.models.masters.waste_masters.property import Property
from app.models.masters.waste_masters.subproperty import SubProperty


class UserChargeRuleSeeder(BaseSeeder):
    name = "UserChargeRuleSeeder"

    # (property_name, sub_property_name, min_sqmtr, max_sqmtr, charge_amount, is_bulk)
    CHARGE_RULES = [
        ("Residential",   "Apartment",       Decimal("0"),    Decimal("50"),   Decimal("100.00"), False),
        ("Residential",   "Apartment",       Decimal("50"),   Decimal("100"),  Decimal("150.00"), False),
        ("Commercial",    "Shop",            Decimal("0"),    Decimal("100"),  Decimal("250.00"), False),
        ("Industrial",    "Factory",         Decimal("0"),    Decimal("500"),  Decimal("500.00"), False),
        ("Government",    "Municipal Office",None,            None,            Decimal("0.00"),   True),
    ]

    def run(self):
        count = 0
        for prop_name, sub_prop_name, min_sq, max_sq, charge, is_bulk in self.CHARGE_RULES:
            property_obj = Property.objects.filter(
                property_name=prop_name, is_deleted=False
            ).first()
            sub_property = SubProperty.objects.filter(
                property_id=property_obj,
                sub_property_name=sub_prop_name,
                is_deleted=False,
            ).first() if property_obj else None

            if not property_obj or not sub_property:
                self.log(f"Property/SubProperty '{prop_name}/{sub_prop_name}' not found — skipping.")
                continue

            exists = UserChargeRule.objects.filter(
                property_id=property_obj,
                subproperty_id=sub_property,
                min_sqmtr_value=min_sq,
                max_sqmtr_value=max_sq,
                is_deleted=False,
            ).exists()
            if exists:
                self.log(f"Charge rule for '{prop_name}/{sub_prop_name}' already exists — skipping.")
                continue

            UserChargeRule.objects.create(
                property_id=property_obj,
                subproperty_id=sub_property,
                min_sqmtr_value=min_sq,
                max_sqmtr_value=max_sq,
                charge_amount=charge,
                is_bulk_waste_generator=is_bulk,
                is_active=True,
                is_deleted=False,
            )
            count += 1

        self.log(f"---User charge rules seeded ({count} created)---")

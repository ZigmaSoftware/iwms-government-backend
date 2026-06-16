from decimal import Decimal

from app.management.commands.seeders.base import BaseSeeder
from app.models.customers.userchargerule import UserChargeRule
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


class UserChargeRuleSeeder(BaseSeeder):
    name = "user_charge_rule"

    # (property_name, subproperty_name, is_bulk, min_sqm, max_sqm, charge, description)
    RULES = [
        # Residential - Apartment
        ("Residential", "Apartment", True,  None,              None,              Decimal("300.00"), "Residential Apartment — bulk generator"),
        ("Residential", "Apartment", False, Decimal("0.00"),   Decimal("1200.00"),Decimal("100.00"), "Residential Apartment — 0–1200 sqm"),
        ("Residential", "Apartment", False, Decimal("1200.01"),Decimal("2500.00"),Decimal("150.00"), "Residential Apartment — 1200–2500 sqm"),
        # Residential - Individual House
        ("Residential", "Individual House", True,  None,              None,              Decimal("250.00"), "Individual House — bulk generator"),
        ("Residential", "Individual House", False, Decimal("0.00"),   Decimal("1000.00"),Decimal("80.00"),  "Individual House — 0–1000 sqm"),
        # Commercial - Office
        ("Commercial",  "Office",    True,  None,              None,              Decimal("500.00"), "Commercial Office — bulk generator"),
        ("Commercial",  "Office",    False, Decimal("0.00"),   Decimal("2000.00"),Decimal("200.00"), "Commercial Office — 0–2000 sqm"),
        ("Commercial",  "Office",    False, Decimal("2000.01"),Decimal("5000.00"),Decimal("350.00"), "Commercial Office — 2000–5000 sqm"),
        # Commercial - Shop
        ("Commercial",  "Shop",      True,  None,              None,              Decimal("400.00"), "Commercial Shop — bulk generator"),
        ("Commercial",  "Shop",      False, Decimal("0.00"),   Decimal("500.00"), Decimal("120.00"), "Commercial Shop — 0–500 sqm"),
        # Industrial - Factory
        ("Industrial",  "Factory",   True,  None,              None,              Decimal("1000.00"),"Industrial Factory — bulk generator"),
        ("Industrial",  "Factory",   False, Decimal("0.00"),   Decimal("5000.00"),Decimal("400.00"), "Industrial Factory — 0–5000 sqm"),
        # Industrial - Warehouse
        ("Industrial",  "Warehouse", True,  None,              None,              Decimal("800.00"), "Industrial Warehouse — bulk generator"),
        ("Industrial",  "Warehouse", False, Decimal("0.00"),   Decimal("3000.00"),Decimal("300.00"), "Industrial Warehouse — 0–3000 sqm"),
        # Institutional - Hospital
        ("Institutional","Hospital", True,  None,              None,              Decimal("600.00"), "Institutional Hospital — bulk generator"),
    ]

    def run(self):
        company = Company.objects.filter(is_deleted=False).first()
        if not company:
            self.log("No company found. Seed company data first.")
            return

        project = Project.objects.filter(company_id=company, is_deleted=False).first()

        property_cache = {}
        subproperty_cache = {}

        for entry in self.RULES:
            prop_name, sub_name, is_bulk, min_sqm, max_sqm, charge, desc = entry

            if prop_name not in property_cache:
                prop = Property.objects.filter(property_name=prop_name, is_deleted=False).first()
                if not prop:
                    self.log(f"Property '{prop_name}' not found — skipping.")
                    continue
                property_cache[prop_name] = prop

            property_obj = property_cache[prop_name]
            cache_key = f"{prop_name}::{sub_name}"

            if cache_key not in subproperty_cache:
                sub = SubProperty.objects.filter(
                    property_id=property_obj,
                    sub_property_name=sub_name,
                    is_deleted=False,
                ).first()
                if not sub:
                    self.log(f"SubProperty '{sub_name}' not found — skipping.")
                    continue
                subproperty_cache[cache_key] = sub

            subproperty_obj = subproperty_cache[cache_key]

            rule, created = UserChargeRule.objects.get_or_create(
                company_id=company,
                project_id=project,
                property_id=property_obj,
                subproperty_id=subproperty_obj,
                is_bulk_waste_generator=is_bulk,
                min_sqmtr_value=min_sqm,
                max_sqmtr_value=max_sqm,
                defaults={
                    "charge_amount": charge,
                    "description": desc,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if not created:
                update_fields = []
                if rule.charge_amount != charge:
                    rule.charge_amount = charge
                    update_fields.append("charge_amount")
                if rule.is_deleted:
                    rule.is_deleted = False
                    update_fields.append("is_deleted")
                if update_fields:
                    rule.save(update_fields=update_fields)

        self.log(f"---UserChargeRules seeded ({len(self.RULES)} records)---")

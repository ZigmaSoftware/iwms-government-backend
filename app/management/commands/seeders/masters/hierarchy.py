from app.management.commands.seeders.base import BaseSeeder

from app.models.masters.areatype import AreaType
from app.models.masters.hierarchy import AdministrativeHierarchy


class AdministrativeHierarchySeeder(BaseSeeder):
    name = "hierarchy"

    # (area_type_name, level_name) — 15 combinations
    HIERARCHY_STRUCTURE = [
        ("Urban",      "Zone"),
        ("Urban",      "Ward"),
        ("Urban",      "Block"),
        ("Urban",      "Street"),
        ("Rural",      "Panchayat"),
        ("Rural",      "Village"),
        ("Rural",      "Hamlet"),
        ("Semi-Urban", "Division"),
        ("Semi-Urban", "Sector"),
        ("Industrial", "Estate"),
        ("Industrial", "Phase"),
        ("Commercial", "Complex"),
        ("Commercial", "Market"),
        ("Coastal",    "Bay"),
        ("Coastal",    "Harbor"),
    ]

    def run(self):
        area_type_cache = {}

        for area_type_name, level_name in self.HIERARCHY_STRUCTURE:
            if area_type_name not in area_type_cache:
                area_type = AreaType.objects.filter(name=area_type_name).first()
                if not area_type:
                    self.log(f"AreaType '{area_type_name}' not found — skipping.")
                    continue
                area_type_cache[area_type_name] = area_type

            area_type = area_type_cache[area_type_name]
            obj, created = AdministrativeHierarchy.objects.get_or_create(
                area_type=area_type,
                level_name=level_name,
            )
            action = "Created" if created else "Exists"
            self.log(f"Hierarchy seeded: {area_type_name} - {level_name} ({action})")

        self.log(f"---Hierarchies seeded ({len(self.HIERARCHY_STRUCTURE)} records)---")

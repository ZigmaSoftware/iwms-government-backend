from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.areatype import AreaType
from app.models.masters.hierarchy import AdministrativeHierarchy


class AdministrativeHierarchySeeder(BaseSeeder):
    name = "hierarchy"

    # (area_type_name, level_name) — 5 records using valid AreaTypeName choices
    HIERARCHY_STRUCTURE = [
        ("Urban Local Body", "Ward"),
        ("Urban Local Body", "Street"),
        ("Urban Local Body", "Zone"),
        ("Rural Local Body", "Panchayat"),
        ("Rural Local Body", "Village"),
    ]

    def run(self):
        area_type_cache = {}
        count = 0

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
            self.log(f"Hierarchy: {area_type_name} - {level_name} ({action})")
            count += 1

        self.log(f"---Hierarchies seeded ({count} records)---")

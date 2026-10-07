from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.common_masters.state import State
from app.models.masters.areatype import AreaType
from app.models.masters.district import District


class LocalBodySeeder(BaseSeeder):
    """Shared run() for the five local-body masters (Corporation,
    Municipality, TownPanchayat, PanchayatUnion, Panchayat): every Tamil
    Nadu body of that type from seeders/tn_local_bodies.py, keyed on
    (district, name) so re-runs update the same rows in place."""

    model = None
    name_field = None
    area_type_name = None
    label = None

    def local_bodies(self):
        """[{"district": name, "name": name, "coordinates": [...]}, ...]"""
        raise NotImplementedError

    def run(self):
        tamil_nadu = State.objects.filter(name="Tamil Nadu").first()
        if not tamil_nadu:
            self.log("Tamil Nadu state not found — run StateSeeder first.")
            return

        districts = {
            d.name: d.unique_id
            for d in District.objects.filter(state_id=tamil_nadu.unique_id, is_deleted=False).order_by("-pk")
        }
        area_types = {}
        for area_type in AreaType.objects.filter(
            state_id=tamil_nadu.unique_id, name=self.area_type_name, is_deleted=False
        ).order_by("pk"):
            area_types.setdefault(area_type.district_id, area_type.unique_id)

        rows, missing = [], set()
        for local_body in self.local_bodies():
            district_id = districts.get(local_body["district"])
            area_type_id = area_types.get(district_id)
            if not area_type_id:
                missing.add(local_body["district"])
                continue
            rows.append({
                "state_id": tamil_nadu.unique_id,
                "district_id": district_id,
                "area_type_id": area_type_id,
                self.name_field: local_body["name"],
                "coordinates": local_body["coordinates"],
                "is_active": True,
                "is_deleted": False,
            })

        for district_name in sorted(missing):
            self.log(f"{self.area_type_name} area type for '{district_name}' not found — skipping.")

        created, updated = self.bulk_upsert(
            self.model, rows,
            key_fields=("district_id", self.name_field),
            scope={"state_id": tamil_nadu.unique_id},
        )
        self.log(f"---{self.label} seeded ({len(rows)} records: {created} created, {updated} updated)---")

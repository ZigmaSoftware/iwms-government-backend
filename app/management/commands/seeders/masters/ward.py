from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.zone import Zone
from app.models.masters.ward import Ward


class WardSeeder(BaseSeeder):
    name = "WardSeeder"

    def run(self):
        zone = Zone.objects.select_related("state_id", "district_id", "city_id").first()
        if not zone:
            self.log("Skipped: no zone found for ward seed data.")
            return

        coordinates = [
            {"latitude": 13.080800, "longitude": 80.273100},
            {"latitude": 13.083200, "longitude": 80.277500},
            {"latitude": 13.079600, "longitude": 80.280100},
            {"latitude": 13.077300, "longitude": 80.275600},
        ]
        ward, created = Ward.objects.update_or_create(
            ward_name="Ward 001",
            zone_id=zone,
            defaults={
                "state_id": zone.state_id,
                "district_id": zone.district_id,
                "city_id": zone.city_id,
                "latitude": coordinates[0]["latitude"],
                "longitude": coordinates[0]["longitude"],
                "geofencing_type": "polygon",
                "coordinates": coordinates,
                "description": "Seeded ward with polygon geofence coordinates.",
                "is_active": True,
            },
        )
        action = "Created" if created else "Updated"
        self.log(f"{action}: {ward.ward_name} with {len(coordinates)} geofence points.")

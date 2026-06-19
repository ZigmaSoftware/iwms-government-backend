from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.city import City
from app.models.masters.zone import Zone


class ZoneSeeder(BaseSeeder):
    name = "ZoneSeeder"

    def run(self):
        city = City.objects.select_related("state_id", "district_id").first()
        if not city:
            self.log("Skipped: no city found for zone seed data.")
            return

        coordinates = [
            {"latitude": 13.082700, "longitude": 80.270700},
            {"latitude": 13.087400, "longitude": 80.279200},
            {"latitude": 13.079100, "longitude": 80.286300},
            {"latitude": 13.073900, "longitude": 80.276600},
        ]
        zone, created = Zone.objects.update_or_create(
            zone_name="Central Zone",
            city_id=city,
            defaults={
                "state_id": city.state_id,
                "district_id": city.district_id,
                "latitude": coordinates[0]["latitude"],
                "longitude": coordinates[0]["longitude"],
                "geofencing_type": "polygon",
                "coordinates": coordinates,
                "description": "Seeded zone with polygon geofence coordinates.",
                "is_active": True,
            },
        )
        action = "Created" if created else "Updated"
        self.log(f"{action}: {zone.zone_name} with {len(coordinates)} geofence points.")

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.city import City
from app.models.masters.panchayat import Panchayat


class PanchayatSeeder(BaseSeeder):
    name = "PanchayatSeeder"

    def run(self):
        city = City.objects.select_related("state_id", "district_id").first()
        if not city:
            self.log("Skipped: no city found for panchayat seed data.")
            return

        coordinates = [
            {"latitude": 12.987100, "longitude": 80.218400},
            {"latitude": 12.991200, "longitude": 80.225300},
            {"latitude": 12.984600, "longitude": 80.231100},
            {"latitude": 12.979800, "longitude": 80.222600},
        ]
        panchayat, created = Panchayat.objects.update_or_create(
            panchayat_name="Sample Panchayat",
            city_id=city,
            defaults={
                "state_id": city.state_id,
                "district_id": city.district_id,
                "latitude": coordinates[0]["latitude"],
                "longitude": coordinates[0]["longitude"],
                "geofencing_type": "polygon",
                "coordinates": coordinates,
                "agreed_weight_kg": "2500.75",
                "weight_unit": "kg",
                "is_active": True,
            },
        )
        action = "Created" if created else "Updated"
        self.log(f"{action}: {panchayat.panchayat_name} with {len(coordinates)} geofence points.")

from app.management.commands.seeders.base import BaseSeeder
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward

WARDS_PER_LOCAL_BODY = 3


class WardSeeder(BaseSeeder):
    name = "WardSeeder"

    LOCAL_BODY_FIELDS = [
        ("corporation", Corporation),
        ("municipality", Municipality),
        ("town_panchayat", TownPanchayat),
        ("panchayat_union", PanchayatUnion),
        ("panchayat", Panchayat),
    ]

    def run(self):
        count = 0
        for field_name, model in self.LOCAL_BODY_FIELDS:
            for local_body in model.objects.all():
                for index in range(1, WARDS_PER_LOCAL_BODY + 1):
                    Ward.objects.update_or_create(
                        **{field_name: local_body},
                        ward_name=f"Ward {index}",
                        defaults={
                            "state": local_body.state_id,
                            "district": local_body.district_id,
                            "area_type": local_body.area_type_id,
                            "coordinates": [],
                            "is_active": True,
                            "is_deleted": False,
                        },
                    )
                    count += 1

        self.log(f"---Wards seeded ({count} records)---")

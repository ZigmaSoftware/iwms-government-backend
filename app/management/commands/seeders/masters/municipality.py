from app.management.commands.seeders import tn_local_bodies
from app.management.commands.seeders.masters.local_body import LocalBodySeeder
from app.models.masters.municipality import Municipality


class MunicipalitySeeder(LocalBodySeeder):
    name = "MunicipalitySeeder"
    model = Municipality
    name_field = "municipality_name"
    area_type_name = "Urban Local Body"
    label = "Municipalities"

    def local_bodies(self):
        return tn_local_bodies.municipalities()

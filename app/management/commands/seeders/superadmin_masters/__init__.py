from .blue_planet import BluePlanetSeeder
from .superuser import PlatformSuperUserSeeder

COMPANY_SEEDERS = []

PLATFORM_SEEDERS = [
    PlatformSuperUserSeeder,
]

SUPERADMIN_MASTER_SEEDERS = COMPANY_SEEDERS + PLATFORM_SEEDERS

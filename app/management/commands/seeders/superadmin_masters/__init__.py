from .blue_planet import BluePlanetSeeder
from .company import CompanySeeder
from .developer import PlatformDeveloperSeeder
from .project import ProjectSeeder
from .superuser import PlatformSuperUserSeeder

COMPANY_SEEDERS = [
    CompanySeeder,
    BluePlanetSeeder,
    ProjectSeeder,
]

PLATFORM_SEEDERS = [
    PlatformSuperUserSeeder,
    PlatformDeveloperSeeder,
]

SUPERADMIN_MASTER_SEEDERS = COMPANY_SEEDERS + PLATFORM_SEEDERS

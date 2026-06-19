from .district import DistrictSeeder
from .areatype import AreaTypeSeeder
from .hierarchy import AdministrativeHierarchySeeder
from .panchayat import PanchayatSeeder

MASTER_SEEDERS = [
    DistrictSeeder,
    AreaTypeSeeder,
    AdministrativeHierarchySeeder,
    PanchayatSeeder,   
]

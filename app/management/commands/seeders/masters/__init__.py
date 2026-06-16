from .district import DistrictSeeder
from .city import CitySeeder
from .zone import ZoneSeeder
from .ward import WardSeeder
from .areatype import AreaTypeSeeder
from .hierarchy import AdministrativeHierarchySeeder
from .panchayat import PanchayatSeeder

MASTER_SEEDERS = [
    DistrictSeeder,
    CitySeeder,
    AreaTypeSeeder,
    AdministrativeHierarchySeeder,
    ZoneSeeder,
    WardSeeder,
    PanchayatSeeder,   
]

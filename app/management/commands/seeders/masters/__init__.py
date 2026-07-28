from .district import DistrictSeeder
from .areatype import AreaTypeSeeder
from .corporation import CorporationSeeder
from .municipality import MunicipalitySeeder
from .hierarchy import AdministrativeHierarchySeeder
from .panchayat import PanchayatSeeder
from .panchayat_union import PanchayatUnionSeeder
from .town_panchayat import TownPanchayatSeeder
from .ward import WardSeeder

MASTER_SEEDERS = [
    DistrictSeeder,
    AreaTypeSeeder,
    CorporationSeeder,
    MunicipalitySeeder,
    TownPanchayatSeeder,
    PanchayatUnionSeeder,
    AdministrativeHierarchySeeder,
    PanchayatSeeder,
    WardSeeder,
]

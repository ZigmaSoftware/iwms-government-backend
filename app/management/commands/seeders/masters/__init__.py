from .district import DistrictSeeder
from .areatype import AreaTypeSeeder
from .corporation import CorporationSeeder
from .hierarchy import AdministrativeHierarchySeeder
from .municipality import MunicipalitySeeder
from .panchayat import PanchayatSeeder
from .panchayat_union import PanchayatUnionSeeder
from .town_panchayat import TownPanchayatSeeder

MASTER_SEEDERS = [
    DistrictSeeder,
    AreaTypeSeeder,
    CorporationSeeder,
    MunicipalitySeeder,
    TownPanchayatSeeder,
    PanchayatUnionSeeder,
    AdministrativeHierarchySeeder,
    PanchayatSeeder,   
]

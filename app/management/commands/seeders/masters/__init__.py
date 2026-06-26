from .district import DistrictSeeder
from .areatype import AreaTypeSeeder
from .corporation import CorporationSeeder
from .hierarchy import AdministrativeHierarchySeeder
from .hierarchy_tree import HierarchyTreeSeeder
from .geo_to_hierarchy import GeoToHierarchySeeder
from .backfill_location_node import BackfillLocationNodeSeeder
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
    HierarchyTreeSeeder,
    PanchayatSeeder,
    # Mirror existing geo masters into the hierarchy AFTER panchayats/districts
    # exist, so geography is available as dynamic nodes...
    GeoToHierarchySeeder,
    # ...then point dependents (customers/staff/users/leaders) at those nodes.
    BackfillLocationNodeSeeder,
]

from .district import DistrictSeeder
from .areatype import AreaTypeSeeder
from .hierarchy import AdministrativeHierarchySeeder
from .hierarchy_tree import HierarchyTreeSeeder
from .geo_to_hierarchy import GeoToHierarchySeeder
from .backfill_location_node import BackfillLocationNodeSeeder
from .panchayat import PanchayatSeeder

MASTER_SEEDERS = [
    DistrictSeeder,
    AreaTypeSeeder,
    AdministrativeHierarchySeeder,
    HierarchyTreeSeeder,
    PanchayatSeeder,
    # Mirror existing geo masters into the hierarchy AFTER panchayats/districts
    # exist, so geography is available as dynamic nodes...
    GeoToHierarchySeeder,
    # ...then point dependents (customers/staff/users/leaders) at those nodes.
    BackfillLocationNodeSeeder,
]

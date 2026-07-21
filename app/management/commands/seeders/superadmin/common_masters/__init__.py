from .continent import ContinentSeeder
from .country import CountrySeeder
from .state import StateSeeder

COMMON_MASTER_SEEDERS = [
    ContinentSeeder,
    CountrySeeder,
    StateSeeder,
]

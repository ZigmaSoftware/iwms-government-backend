from .properties import PropertySeeder
from .subproperties import SubPropertySeeder
from .wastetype import WasteTypeSeeder

WASTE_TYPE_SEEDERS = [
    PropertySeeder,
    SubPropertySeeder,
    WasteTypeSeeder,
]

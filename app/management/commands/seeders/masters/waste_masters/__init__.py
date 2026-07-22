from .bins import BinSeeder
from .wastetype import WasteTypeSeeder
from .properties import PropertySeeder
from .subproperties import SubPropertySeeder

WASTE_MASTERS_SEEDERS = [
    PropertySeeder,
    SubPropertySeeder,
    WasteTypeSeeder,
    BinSeeder,
]

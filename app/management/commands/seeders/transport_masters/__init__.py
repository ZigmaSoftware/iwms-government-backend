from .fuel import FuelSeeder
from .trip_attendance import TripAttendanceSeeder
from .vehicleCreation import VehicleCreationSeeder
from .vehicleTypeCreation import VehicleTypeCreationSeeder

TRANSPORT_MASTER_SEEDERS = [
    FuelSeeder,
    VehicleTypeCreationSeeder,
    VehicleCreationSeeder,
    TripAttendanceSeeder,
]

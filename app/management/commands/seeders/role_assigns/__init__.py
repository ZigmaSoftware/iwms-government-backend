from .contractorUserType import ContractorUserTypeSeeder
from .staffUserType import StaffUserTypeSeeder
from .userType import UserTypeSeeder

ROLE_ASSIGN_SEEDERS = [
    UserTypeSeeder,
    StaffUserTypeSeeder,
    ContractorUserTypeSeeder,
]

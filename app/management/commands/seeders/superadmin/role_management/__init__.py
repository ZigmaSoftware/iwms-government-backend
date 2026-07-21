from .governmentStaffUserType import GovernmentStaffUserTypeSeeder
from .userType import UserTypeSeeder

ROLE_ASSIGN_SEEDERS = [
    UserTypeSeeder,
    GovernmentStaffUserTypeSeeder,
]

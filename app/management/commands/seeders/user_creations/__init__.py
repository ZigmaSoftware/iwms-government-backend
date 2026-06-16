from .auth_user_seeder import AuthUserSeeder
from .staff_office import StaffOfficeSeeder
from .staff_personal import StaffPersonalSeeder


USER_CREATION_SEEDERS = [
    StaffOfficeSeeder,
    StaffPersonalSeeder,
    
]

STAFF_TEMPLATE_SEEDERS = [
    AuthUserSeeder,
]



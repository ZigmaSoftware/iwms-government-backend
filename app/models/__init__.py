"""
Aggregate exports for the models package.
Structured to mirror API router groupings.
"""

# ============================================================
# GROUP: COMMON MASTERS
# ============================================================
from .common_masters.continent import Continent
from .common_masters.country import Country
from .common_masters.state import State


# ============================================================
# GROUP: MASTERS
# ============================================================
from .masters.district import District
from .masters.city import City
from .masters.zone import Zone
from .masters.ward import Ward
from .masters.department import Department
from .masters.designation import Designation
from .masters.panchayat_leader_login import PanchayatLeaderLogin
from .masters.municipality import Municipality
from .masters.town_panchayat import TownPanchayat
from .masters.block_panchayat_union import BlockPanchayatUnion


# ============================================================
# GROUP: ASSETS
# ============================================================
from .transport_masters.fuel import Fuel


# ============================================================
# GROUP: TENANCY / SUPERADMIN
# ============================================================
from .superadmin_masters.auth_user import User


# ============================================================
# GROUP: WASTE TYPES
# ============================================================
from .waste_types.property import Property
from .waste_types.subproperty import SubProperty

# ============================================================
# GROUP: USERS & ROLE ASSIGNMENT
# ============================================================
from .role_assigns.userType import UserType
from .role_assigns.staffUserType import StaffUserType


# ============================================================
# GROUP: SCREEN MANAGEMENT / PERMISSIONS
# ============================================================
from .screen_managements.mainscreentype import MainScreenType
from .screen_managements.mainscreen import MainScreen
from .screen_managements.userscreen import UserScreen
from .screen_managements.userscreenaction import UserScreenAction
from .screen_managements.userscreencolumn import UserScreenColumn
from .screen_managements.companyuserscreenpermission import (
    CompanyUserScreenPermission,
    UserScreenPermission,
)
from .screen_managements.companyuserscreencolumnpermission import CompanyUserScreenColumnPermission


# ============================================================
# GROUP: USER CREATION & STAFF
# ============================================================
from .user_creations.staffcreation import (
    StaffcreationOfficeDetails,
    StaffPersonalDetails,
)
from .schedule_masters.staff_template import StaffTemplate
from .schedule_masters.alternative_staff_template import AlternativeStaffTemplate
from .user_creations.unassigned_staff_pool import UnassignedStaffPool


# ============================================================
# GROUP: AUTH / LOGIN / AUDIT (USER)
# ============================================================
from .user_creations.loginAudit import LoginAudit
from .user_creations.auditlog import AuditLog
from app.utils.common_audit import CommonAudit
from .audits.permission_audit import PermissionAuditLog
from .audits.supervisor_zone_access_audit import SupervisorZoneAccessAudit
from .user_creations.supervisor_zone_map import SupervisorZoneMap


# ============================================================
# GROUP: CUSTOMER MODULES
# ============================================================
from .customers.customercreation import CustomerCreation
from .customers.wastecollection import WasteCollection
from .customers.feedback import FeedBack
from .customers.userchargerule import UserChargeRule
from .customers.password_reset_otp import PasswordResetOTP


# ============================================================
# GROUP: GRIEVANCES
# ============================================================
from .grivences.complaints import Complaint
from .grivences.main_category_citizenGrievance import MainCategory
from .grivences.sub_category_citizenGrievance import SubCategory


# ============================================================
# GROUP: BLUETOOTH / MOBILE WASTE COLLECTION
# ============================================================
from .user_creations.waste_collection_bluetooth import (
    WasteCollectionSub,
    WasteType,
    WasteCollectionMain,
)


# ============================================================
# GROUP: ATTENDANCE (MOBILE)
# ============================================================
from .user_creations.attendance import Employee, Recognized


# ============================================================
# GROUP: TRANSPORT MASTERS & TRIPS
# ============================================================
from .transport_masters.vehicleTypeCreation import VehicleTypeCreation
from .transport_masters.vehicleCreation import VehicleCreation
from .schedule_masters.trip_plan import TripPlan
from .schedule_masters.trip_plan_collection_point import TripPlanCollectionPoint
from .transport_masters.trip_attendance import TripAttendance
from .schedule_masters.daily_trip_assignment import DailyTripAssignment
from .schedule_masters.daily_trip_log import DailyTripLog
from .schedule_masters.daily_trip_collection_point import DailyTripCollectionPoint
from .schedule_masters.daily_trip_household_collection import DailyTripHouseholdCollection
from .schedule_masters.bin_collection_event import BinCollectionEvent


# ============================================================
# EXPORTS
# ============================================================
__all__ = [
    # Common Masters
    "Continent",
    "Country",
    "State",

    # Masters
    "District",
    "City",
    "Zone",
    "Ward",
    "Department",
    "Designation",
    "PanchayatLeaderLogin",
    "Municipality",
    "TownPanchayat",
    "BlockPanchayatUnion",

    # Assets
    "Fuel",

    # Tenancy
    "User",

    # Waste Types
    "Property",
    "SubProperty",

    # Users & Roles
    "UserType",
    "StaffUserType",

    # Screen Management
    "MainScreenType",
    "MainScreen",
    "UserScreen",
    "UserScreenAction",
    "UserScreenColumn",
    "UserScreenPermission",
    "CompanyUserScreenPermission",
    "CompanyUserScreenColumnPermission",

    # User Creation & Staff
    "StaffcreationOfficeDetails",
    "StaffPersonalDetails",
    "StaffTemplate",
    "AlternativeStaffTemplate",
    "SupervisorZoneMap",
    "UnassignedStaffPool",

    # Auth / Audit
    "LoginAudit",
    "AuditLog",

    # Customers
    "CustomerCreation",
    "WasteCollection",
    "FeedBack",
    "UserChargeRule",
    "PasswordResetOTP",

    # Grievances
    "Complaint",
    "MainCategory",
    "SubCategory",

    # Bluetooth Waste
    "WasteCollectionSub",
    "WasteType",
    "WasteCollectionMain",

    # Attendance
    "Employee",
    "Recognized",

    # Transport
    "VehicleTypeCreation",
    "VehicleCreation",
    "TripPlan",
    "TripPlanCollectionPoint",
    "TripAttendance",

    # Audits
    "PermissionAuditLog",
    "SupervisorZoneAccessAudit",

    # Daily Trip Assignment
    "DailyTripAssignment",
    "DailyTripLog",
    "DailyTripCollectionPoint",
    "DailyTripHouseholdCollection",
    "BinCollectionEvent",
]

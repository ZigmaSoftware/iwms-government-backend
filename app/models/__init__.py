"""
Aggregate exports for the models package.
Structured to mirror API router groupings.
"""

# ============================================================
# GROUP: COMMON MASTERS
# ============================================================
from .superadmin.common_masters.continent import Continent
from .superadmin.common_masters.country import Country
from .superadmin.common_masters.state import State


# ============================================================
# GROUP: MASTERS
# ============================================================
from .masters.district import District
from .masters.department import Department
from .masters.designation import Designation
from .masters.leader_management.panchayat_leader_login import PanchayatLeaderLogin
from .masters.leader_management.district_leader_login import DistrictLeaderLogin
from .masters.leader_management.state_leader_login import StateLeaderLogin
from .masters.areatype import AreaType
from .masters.corporation import Corporation
from .masters.municipality import Municipality
from .masters.town_panchayat import TownPanchayat
from .masters.panchayat_union import PanchayatUnion
from .masters.panchayat import Panchayat
from .masters.hierarchy_tree import HierarchyLevel, HierarchyNode, HierarchyClosure
from .masters.hierarchy_assignment import HierarchyAssignment


# ============================================================
# GROUP: ASSETS
# ============================================================
from .masters.transport_masters.fuel import Fuel


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
from .superadmin.role_management.userType import UserType
from .superadmin.role_management.staffUserType import StaffUserType
from .superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType


# ============================================================
# GROUP: SCREEN MANAGEMENT / PERMISSIONS
# ============================================================
from .superadmin.screen_management.mainscreentype import MainScreenType
from .superadmin.screen_management.mainscreen import MainScreen
from .superadmin.screen_management.userscreen import UserScreen
from .superadmin.screen_management.userscreenaction import UserScreenAction
from .superadmin.screen_management.userscreencolumn import UserScreenColumn
from .superadmin.screen_management.companyuserscreenpermission import (
    CompanyUserScreenPermission,
    UserScreenPermission,
)
from .superadmin.screen_management.companyuserscreencolumnpermission import CompanyUserScreenColumnPermission
from .superadmin.screen_management.dashboardwidgetpermission import DashboardWidgetPermission


# ============================================================
# GROUP: USER CREATION & STAFF
# ============================================================
from .user_creations.staffcreation import (
    StaffcreationOfficeDetails,
    StaffPersonalDetails,
)
from .core_modules.schedule_setup.staff_template import StaffTemplate
from .core_modules.schedule_setup.alternative_staff_template import AlternativeStaffTemplate
from .user_creations.unassigned_staff_pool import UnassignedStaffPool
from .user_creations.staff_data_scope import StaffDataScope


# ============================================================
# GROUP: AUTH / LOGIN / AUDIT (USER)
# ============================================================
from .superadmin.audits.login_audit import LoginAudit
from .superadmin.audits.audit_log import AuditLog
from app.utils.common_audit import CommonAudit
from .superadmin.audits.permission_audit import PermissionAuditLog


# ============================================================
# GROUP: CUSTOMER MODULES
# ============================================================
from .masters.customer_masters.customercreation import CustomerCreation
from .masters.customer_masters.wastecollection import WasteCollection
from .masters.customer_masters.feedback import FeedBack
from .masters.customer_masters.userchargerule import UserChargeRule
from .masters.customer_masters.password_reset_otp import PasswordResetOTP


# ============================================================
# GROUP: COMPLAINT TICKETING
# ============================================================
from .core_modules.complaint_management.source_master import ComplaintSource
from .core_modules.complaint_management.language_master import ComplaintLanguage
from .core_modules.complaint_management.priority_master import ComplaintPriority
from .core_modules.complaint_management.status_master import ComplaintStatus
from .core_modules.complaint_management.module_master import ComplaintModule
from .core_modules.complaint_management.category_master import ComplaintCategory
from .core_modules.complaint_management.subcategory_master import ComplaintSubcategory
from .core_modules.complaint_management.team_master import ComplaintTeam
from .core_modules.complaint_management.sla_rule_master import ComplaintSlaRule
from .core_modules.complaint_management.routing_rule import ComplaintRoutingRule
from .core_modules.complaint_management.ticket import ComplaintTicket
from .core_modules.complaint_management.ticket_extra_detail import ComplaintTicketExtraDetail
from .core_modules.complaint_management.ticket_attachment import ComplaintAttachment
from .core_modules.complaint_management.status_history import ComplaintStatusHistory
from .core_modules.complaint_management.assignment_history import ComplaintAssignmentHistory
from .core_modules.complaint_management.escalation_history import ComplaintEscalationHistory
from .core_modules.complaint_management.reopen_history import ComplaintReopenHistory
from .core_modules.complaint_management.comment import ComplaintComment
from .core_modules.complaint_management.feedback import ComplaintFeedback
from .core_modules.complaint_management.address_change_request import ComplaintAddressChangeRequest
from .core_modules.complaint_management.notification import ComplaintNotification


# ============================================================
# GROUP: BLUETOOTH / MOBILE WASTE COLLECTION
# ============================================================
from .user_creations.waste_collection_bluetooth import (
    WasteCollectionSub,
    WasteCollectionMain,
)
from .assets.wastetype import WasteType


# ============================================================
# GROUP: ATTENDANCE (MOBILE)
# ============================================================
from .core_modules.attendance import DailyAttendanceReg


# ============================================================
# GROUP: TRANSPORT MASTERS & TRIPS
# ============================================================
from .masters.transport_masters.vehicleTypeCreation import VehicleTypeCreation
from .masters.transport_masters.vehicleCreation import VehicleCreation
from .core_modules.schedule_setup.trip_plan import TripPlan
from .core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
from .masters.transport_masters.trip_attendance import TripAttendance
from .core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from .core_modules.daily_operations.daily_trip_log import DailyTripLog
from .core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
from .core_modules.daily_operations.daily_trip_household_collection import DailyTripHouseholdCollection
from .core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent
from .schedule_masters.scheduler_config import SchedulerConfig
from .core_modules.daily_operations.vehicle_breakdown import VehicleBreakdown


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
    "AreaType",
    "Corporation",
    "Department",
    "Designation",
    "PanchayatLeaderLogin",
    "DistrictLeaderLogin",
    "StateLeaderLogin",
    "Municipality",
    "TownPanchayat",
    "PanchayatUnion",
    "Panchayat",

    # Hierarchy Tree (closure-table)
    "HierarchyLevel",
    "HierarchyNode",
    "HierarchyClosure",
    "HierarchyAssignment",

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
    "GovernmentStaffUserType",

    # Screen Management
    "MainScreenType",
    "MainScreen",
    "UserScreen",
    "UserScreenAction",
    "UserScreenColumn",
    "UserScreenPermission",
    "CompanyUserScreenPermission",
    "CompanyUserScreenColumnPermission",
    "DashboardWidgetPermission",

    # User Creation & Staff
    "StaffcreationOfficeDetails",
    "StaffPersonalDetails",
    "StaffTemplate",
    "AlternativeStaffTemplate",
    "UnassignedStaffPool",
    "StaffDataScope",

    # Auth / Audit
    "LoginAudit",
    "AuditLog",

    # Customers
    "CustomerCreation",
    "WasteCollection",
    "FeedBack",
    "UserChargeRule",
    "PasswordResetOTP",

    # Complaint Ticketing
    "ComplaintSource",
    "ComplaintLanguage",
    "ComplaintPriority",
    "ComplaintStatus",
    "ComplaintCategory",
    "ComplaintSubcategory",
    "ComplaintTeam",
    "ComplaintSlaRule",
    "ComplaintRoutingRule",
    "ComplaintTicket",
    "ComplaintTicketExtraDetail",
    "ComplaintAttachment",
    "ComplaintStatusHistory",
    "ComplaintAssignmentHistory",
    "ComplaintEscalationHistory",
    "ComplaintReopenHistory",
    "ComplaintComment",
    "ComplaintFeedback",
    "ComplaintAddressChangeRequest",

    # Bluetooth Waste
    "WasteCollectionSub",
    "WasteType",
    "WasteCollectionMain",

    # Attendance
    "DailyAttendanceReg",

    # Transport
    "VehicleTypeCreation",
    "VehicleCreation",
    "TripPlan",
    "TripPlanCollectionPoint",
    "TripAttendance",

    # Audits
    "PermissionAuditLog",

    # Daily Trip Assignment
    "DailyTripAssignment",
    "DailyTripLog",
    "DailyTripCollectionPoint",
    "DailyTripHouseholdCollection",
    "BinCollectionEvent",
]

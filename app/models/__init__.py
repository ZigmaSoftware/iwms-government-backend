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
from .masters.department import Department
from .masters.designation import Designation
from .masters.panchayat_leader_login import PanchayatLeaderLogin
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
from .role_assigns.governmentStaffUserType import GovernmentStaffUserType


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


# ============================================================
# GROUP: CUSTOMER MODULES
# ============================================================
from .customers.customercreation import CustomerCreation
from .customers.wastecollection import WasteCollection
from .customers.feedback import FeedBack
from .customers.userchargerule import UserChargeRule
from .customers.password_reset_otp import PasswordResetOTP


# ============================================================
# GROUP: COMPLAINT TICKETING
# ============================================================
from .complaint_ticket.source_master import ComplaintSource
from .complaint_ticket.language_master import ComplaintLanguage
from .complaint_ticket.priority_master import ComplaintPriority
from .complaint_ticket.status_master import ComplaintStatus
from .complaint_ticket.category_master import ComplaintCategory
from .complaint_ticket.subcategory_master import ComplaintSubcategory
from .complaint_ticket.team_master import ComplaintTeam
from .complaint_ticket.sla_rule_master import ComplaintSlaRule
from .complaint_ticket.routing_rule import ComplaintRoutingRule
from .complaint_ticket.ticket import ComplaintTicket
from .complaint_ticket.ticket_extra_detail import ComplaintTicketExtraDetail
from .complaint_ticket.ticket_attachment import ComplaintAttachment
from .complaint_ticket.status_history import ComplaintStatusHistory
from .complaint_ticket.assignment_history import ComplaintAssignmentHistory
from .complaint_ticket.escalation_history import ComplaintEscalationHistory
from .complaint_ticket.reopen_history import ComplaintReopenHistory
from .complaint_ticket.comment import ComplaintComment
from .complaint_ticket.feedback import ComplaintFeedback
from .complaint_ticket.address_change_request import ComplaintAddressChangeRequest


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
    "AreaType",
    "Corporation",
    "Department",
    "Designation",
    "PanchayatLeaderLogin",
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

    # User Creation & Staff
    "StaffcreationOfficeDetails",
    "StaffPersonalDetails",
    "StaffTemplate",
    "AlternativeStaffTemplate",
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

    # Daily Trip Assignment
    "DailyTripAssignment",
    "DailyTripLog",
    "DailyTripCollectionPoint",
    "DailyTripHouseholdCollection",
    "BinCollectionEvent",
]

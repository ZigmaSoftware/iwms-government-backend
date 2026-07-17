from django.urls import include, path

from .custom_router import GroupedRouter

# ============================================================
# IMPORTS
# ============================================================

# Common masters
from ..viewsets.common_masters.continent_viewset import ContinentViewSet
from ..viewsets.common_masters.country_viewset import CountryViewSet
from ..viewsets.common_masters.state_viewset import StateViewSet

# Masters
from ..viewsets.masters.district_viewset import DistrictViewSet
from ..viewsets.masters.panchayat_viweset import PanhayatViewSet
from ..viewsets.leader_login.panchayat_leader_viewset import PanchayatLeaderLoginViewSet
from ..viewsets.leader_login.district_leader_viewset import DistrictLeaderLoginViewSet
from ..viewsets.leader_login.state_leader_viewset import StateLeaderLoginViewSet
from ..viewsets.masters.areatype_viewset import AreaTypeViewSet
from ..viewsets.masters.hierarchy_viewset import AdministrativeHierarchyViewSet
from ..viewsets.masters.department_viewset import DepartmentViewSet
from ..viewsets.masters.designation_viewset import DesignationViewSet
from ..viewsets.masters.corporation_viewset import CorporationViewSet
from ..viewsets.masters.municipality_viewset import MunicipalityViewSet
from ..viewsets.masters.town_panchayat_viewset import TownPanchayatViewSet
from ..viewsets.masters.panchayat_union_viewset import PanchayatUnionViewSet

# Waste types
from ..viewsets.waste_types.property_viewset import PropertyViewSet
from ..viewsets.waste_types.subproperty_viewset import SubPropertyViewSet

# Assets
from ..viewsets.assets.wastetype_viewset import WasteTypeViewSet
from ..viewsets.assets.bins_viewset import BinsViewSet

# Screen management
from ..viewsets.screen_managements.mainscreentype_viewset import MainScreenTypeViewSet
from ..viewsets.screen_managements.mainscreen_viewset import MainScreenViewSet
from ..viewsets.screen_managements.userscreen_viewset import UserScreenViewSet
from ..viewsets.screen_managements.userscreenaction_viewset import UserScreenActionViewSet
from ..viewsets.screen_managements.companyuserscreenpermission_viewset import UserScreenPermissionViewSet
from ..viewsets.screen_managements.companyuserscreencolumnpermission_viewset import CompanyUserScreenColumnPermissionViewSet
from ..viewsets.screen_managements.dashboardwidgetpermission_viewset import DashboardWidgetPermissionViewSet
from ..viewsets.screen_managements.permission_api_views import (
    PermissionAssignAPIView,
    UserScreenColumnsAPIView,
    UserPermissionsAPIView,
)

# Role assignments
from ..viewsets.role_assigns.usertype_viewset import UserTypeViewSet
from ..viewsets.role_assigns.staffusertype_viewset import StaffUserTypeViewSet
from ..viewsets.role_assigns.contractorusertype_viewset import ContractorUserTypeViewSet
from ..viewsets.role_assigns.governmentstaffusertype_viewset import GovernmentStaffUserTypeViewSet

# User creations
from ..viewsets.user_creations.staff_viewset import StaffViewSet
from ..viewsets.user_creations.staffcreation_viewset import StaffcreationViewset
from ..viewsets.user_creations.staff_access_configuration_viewset import StaffAccessConfigurationViewSet
from ..viewsets.user_creations.unassigned_staff_pool_viewset import UnassignedStaffPoolViewSet

# Authentication
from ..viewsets.login.login_viewset import LoginViewSet as DesktopLoginViewSet
from ..viewsets.login.permission_viewset import PermissionViewSet
from ..viewsets.auth.forgot_password_viewset import (
    ForgotPasswordView,
    VerifyOTPView,
    ResetPasswordView,
)
from ..viewsets.auth.change_password_viewset import (
    ChangePasswordView,
    AdminChangePasswordView,
)

# Customer modules
from ..viewsets.customers.customercreation_viewset import CustomerCreationViewSet
from ..viewsets.customers.wastecollection_viewset import WasteCollectionViewSet
from ..viewsets.customers.feedback_viewset import FeedBackViewSet
from ..viewsets.customers.userchargerule_viewset import UserChargeRuleViewSet

# Complaint Ticketing
from ..viewsets.complaint_ticket.master_viewsets import (
    ComplaintSourceViewSet,
    ComplaintLanguageViewSet,
    ComplaintPriorityViewSet,
    ComplaintStatusViewSet,
    ComplaintTeamViewSet,
    ComplaintModuleViewSet,
    ComplaintCategoryViewSet,
    ComplaintSubcategoryViewSet,
    ComplaintSlaRuleViewSet,
)
from ..viewsets.complaint_ticket.ticket_viewset import ComplaintTicketViewSet
from ..viewsets.complaint_ticket.citizen_viewset import (
    CitizenComplaintTicketViewSet,
    PublicGrievanceViewSet,
)
from ..viewsets.complaint_ticket.address_change_viewset import ComplaintAddressChangeViewSet
from ..viewsets.complaint_ticket.secondary_viewsets import (
    ComplaintRoutingRuleViewSet,
    ComplaintFeedbackViewSet,
    ComplaintReopenHistoryViewSet,
)
from ..viewsets.complaint_ticket.notification_viewset import ComplaintNotificationViewSet

# Transport masters
from ..viewsets.transport_masters.vehicletypecreation_viewset import VehicleTypeCreationViewSet
from ..viewsets.transport_masters.vehicleCreation_viewset import VehicleCreationViewSet
from ..viewsets.transport_masters.trip_attendance_viewset import TripAttendanceViewSet
from ..viewsets.transport_masters.fuel_viewset import FuelViewSet

# Schedule masters
from ..viewsets.schedule_masters.staff_template_viewset import StaffTemplateViewSet
from ..viewsets.schedule_masters.alternative_staff_template_viewset import AlternativeStaffTemplateViewSet
from ..viewsets.schedule_masters.collection_point_viewset import CollectionPointViewSet
from ..viewsets.schedule_masters.trip_plan_viewset import TripPlanViewSet
from ..viewsets.schedule_masters.daily_trip_assignment_viewset import DailyTripAssignmentViewSet
from ..viewsets.schedule_masters.daily_trip_collection_point_viewset import DailyTripCollectionPointViewSet
from ..viewsets.schedule_masters.daily_trip_household_collection_viewset import DailyTripHouseholdCollectionViewSet
from ..viewsets.schedule_masters.secondary_bin_collection_event_viewset import BinCollectionEventViewSet
from ..viewsets.schedule_masters.vehicle_breakdown_viewset import VehicleBreakdownViewSet
from ..viewsets.schedule_masters.daily_trip_log_viewset import DailyTripLogViewSet
from ..viewsets.schedule_masters.monthly_waste_comparison_viewset import MonthlyWasteComparisonReportViewSet
from ..viewsets.schedule_masters.daily_waste_comparison_viewset import DailyWasteComparisonViewSet

# Audits
from ..viewsets.audits.login_audit_viewset import LoginAuditViewSet
from ..viewsets.audits.common_audit_viewset import CommonAuditViewSet

# Localbody
from ..viewsets.localbody.localbody_dashboard_viewset import LocalBodyDashboardViewSet

# Districtbody
from ..viewsets.districtbody.districtbody_dashboard_viewset import DistrictBodyDashboardViewSet

# Statebody
from ..viewsets.statebody.statebody_dashboard_viewset import StateBodyDashboardViewSet
from ..viewsets.statebody.statebody_waste_comparison_viewset import (
    StateMonthlyWasteComparisonViewSet,
    StateDailyWasteComparisonViewSet,
)

# Operator mobile
from ..viewsets.operator_mobile.my_trip_today_viewset import (
    MyTripTodayViewSet,
    MyTripsTodayViewSet,
)
from ..viewsets.operator_mobile.validate_bin_qr_viewset import ValidateBinQrViewSet
from ..viewsets.operator_mobile.scan_bin_viewset import ScanBinViewSet
from ..viewsets.operator_mobile.trip_history_viewset import TripHistoryViewSet

# Waste bluetooth
from ..viewsets.waste_collection_bluetooth.waste_bluetooth_viewset import WasteCollectionBluetoothViewSet
from ..viewsets.waste_collection_bluetooth.waste_collection_sub_viewset import WasteCollectionSubViewSet
from ..viewsets.waste_collection_bluetooth.waste_collection_main_viewset import WasteCollectionMainViewSet

# Mobile
from ..viewsets.attendance_view.register import RegisterViewSet
from ..viewsets.attendance_view.recognize import RecognizeViewSet
from ..viewsets.attendance_view.employee_viewset import EmployeeViewSet
from ..viewsets.attendance_view.staff_profile_viewset import StaffProfileViewSet
from ..viewsets.attendance_view.attendance_list import AttendanceListViewSet
from ..viewsets.attendance_view.external_attendance import ExternalAttendanceViewSet


router = GroupedRouter()

# ============================================================
# GROUP: COMMON MASTERS
# ============================================================
router.register_group("common-masters", "continents",    ContinentViewSet)
router.register_group("common-masters", "countries",     CountryViewSet)
router.register_group("common-masters", "states",        StateViewSet)

# ============================================================
# GROUP: MASTERS
# ============================================================
router.register_group("masters", "districts",     DistrictViewSet)
router.register_group("masters", "panchayat",         PanhayatViewSet)
router.register_group("masters", "panchayat-leaders", PanchayatLeaderLoginViewSet)
router.register_group("masters", "district-leaders", DistrictLeaderLoginViewSet)
router.register_group("masters", "state-leaders",    StateLeaderLoginViewSet)
router.register_group("masters", "areatypes",         AreaTypeViewSet)
router.register_group("masters", "hierarchy",         AdministrativeHierarchyViewSet)
router.register_group("masters", "departments",       DepartmentViewSet)
router.register_group("masters", "designations",      DesignationViewSet)
router.register_group("masters", "corporations",           CorporationViewSet)
router.register_group("masters", "municipalities",          MunicipalityViewSet)
router.register_group("masters", "town-panchayats",         TownPanchayatViewSet)
router.register_group("masters", "panchayat-unions",        PanchayatUnionViewSet)

# ============================================================
# GROUP: Waste-Type
# ============================================================
router.register_group("waste-types", "properties",    PropertyViewSet)
router.register_group("waste-types", "subproperties", SubPropertyViewSet)

# ============================================================
# GROUP: Assets
# ============================================================
router.register_group("assets","waste-types", WasteTypeViewSet)
router.register_group("assets", "bins", BinsViewSet)

# ============================================================
# GROUP: SCREEN MANAGEMENT (separate group)
# ============================================================
router.register_group("screen-managements", "mainscreentype",        MainScreenTypeViewSet)
router.register_group("screen-managements", "mainscreens",           MainScreenViewSet)
router.register_group("screen-managements", "userscreens",           UserScreenViewSet)
router.register_group("screen-managements", "userscreen-action",     UserScreenActionViewSet)
router.register_group("screen-managements", "userscreenpermissions", UserScreenPermissionViewSet)
router.register_group(
    "screen-managements",
    "companywisescreenpermissions",
    UserScreenPermissionViewSet,
    basename="screen-managements-companywisescreenpermissions-legacy",
)
router.register_group("screen-managements", "column-permissions", CompanyUserScreenColumnPermissionViewSet)
router.register_group("screen-managements", "dashboard-widget-permissions", DashboardWidgetPermissionViewSet)

# ============================================================
# GROUP: USER & ROLE ASSIGNMENT 
# ============================================================
router.register_group("role-assigns", "user-type",           UserTypeViewSet)
router.register_group("role-assigns", "staffusertypes",      StaffUserTypeViewSet)
router.register_group("role-assigns", "staffusertypes",      StaffUserTypeViewSet, basename="staffusertype-roletype")
router.register_group("role-assigns", "contractorusertypes", ContractorUserTypeViewSet)
router.register_group("role-assigns", "contractorusertypes", ContractorUserTypeViewSet, basename="contractorusertype-roletype")
router.register_group("role-assigns", "governmentusertypes", GovernmentStaffUserTypeViewSet)
router.register_group("role-assigns", "governmentusertypes", GovernmentStaffUserTypeViewSet, basename="governmentusertype-roletype")

# ============================================================
# GROUP: USER CREATION
# ============================================================
router.register_group("user-creations", "users-creation",  StaffViewSet)
router.register_group("user-creations", "staffcreation",   StaffcreationViewset)
router.register_group("user-creations", "staff-access-configuration", StaffAccessConfigurationViewSet)

# ============================================================
# GROUP: AUTHENTICATION
# ============================================================
router.register_group("login", "login-user",      DesktopLoginViewSet)
router.register_group("login", "my-permissions",     PermissionViewSet, basename="user-permissions")

# ============================================================
# GROUP: CUSTOMER MODULES
# ============================================================
router.register_group("customer-masters", "customercreations", CustomerCreationViewSet)
router.register_group("schedule-masters", "wastecollections",  WasteCollectionViewSet)
router.register_group("customer-masters", "feedbacks",         FeedBackViewSet)
router.register_group("customer-masters", "user-charge-rules", UserChargeRuleViewSet)

# ============================================================
# GROUP: COMPLAINT TICKETING
# ============================================================
router.register_group("complaint-ticket", "tickets", ComplaintTicketViewSet)
router.register_group("complaint-ticket", "modules", ComplaintModuleViewSet)
router.register_group("complaint-ticket", "categories", ComplaintCategoryViewSet)
router.register_group("complaint-ticket", "subcategories", ComplaintSubcategoryViewSet)
router.register_group("complaint-ticket", "priorities", ComplaintPriorityViewSet)
router.register_group("complaint-ticket", "statuses", ComplaintStatusViewSet)
router.register_group("complaint-ticket", "sources", ComplaintSourceViewSet)
router.register_group("complaint-ticket", "languages", ComplaintLanguageViewSet)
router.register_group("complaint-ticket", "teams", ComplaintTeamViewSet)
router.register_group("complaint-ticket", "sla-rules", ComplaintSlaRuleViewSet)
router.register_group("complaint-ticket", "routing-rules", ComplaintRoutingRuleViewSet)
router.register_group("complaint-ticket", "feedback", ComplaintFeedbackViewSet)
router.register_group("complaint-ticket", "reopen-history", ComplaintReopenHistoryViewSet)
router.register_group("complaint-ticket", "notifications", ComplaintNotificationViewSet, basename="complaint-notifications")
router.register_group("complaint-ticket", "address-change", ComplaintAddressChangeViewSet)

# ============================================================
# GROUP: CITIZEN (mobile app, auth-only — no module permission check)
# ============================================================
router.register_group(
    "citizen",
    "complaint-tickets",
    CitizenComplaintTicketViewSet,
    basename="citizen-complaint-tickets",
)
router.register_group(
    "public",
    "publicgrievance" ,
    PublicGrievanceViewSet,
    basename="publicgrievance",
    include_group_in_prefix=False,
)

# ============================================================
# GROUP: TRANSPORT MASTERS
# ============================================================
router.register_group("transport-masters", "vehicle-type",     VehicleTypeCreationViewSet)
router.register_group("transport-masters", "vehicle-creation", VehicleCreationViewSet)
router.register_group("transport-masters", "trip-attendance", TripAttendanceViewSet)
router.register_group("transport-masters", "fuels",         FuelViewSet)

# ============================================================
# GROUP: SCHEDULE MASTERS
# ============================================================
router.register_group("schedule-masters", "staff-templates", StaffTemplateViewSet)
router.register_group("schedule-masters", "alternative-staff-templates", AlternativeStaffTemplateViewSet)
router.register_group("schedule-masters", "collection-points", CollectionPointViewSet)
router.register_group("schedule-masters", "trip-plans", TripPlanViewSet)
router.register_group("schedule-masters", "daily-trip-assignments", DailyTripAssignmentViewSet)
router.register_group("schedule-masters", "daily-trip-collection-points", DailyTripCollectionPointViewSet)
router.register_group("schedule-masters", "daily-trip-household-collections", DailyTripHouseholdCollectionViewSet)
router.register_group("schedule-masters", "bin-collection-events", BinCollectionEventViewSet)
router.register_group("schedule-masters", "vehicle-breakdowns", VehicleBreakdownViewSet)
router.register_group("schedule-masters", "daily-waste-comparisons", DailyWasteComparisonViewSet)
router.register_group("schedule-masters", "daily-trip-logs", DailyTripLogViewSet)
router.register_group("schedule-masters", "monthly-waste-comparison", MonthlyWasteComparisonReportViewSet, basename="monthly-waste-comparison")

# ============================================================
# GROUP: REPORTS (aliases used by the admin frontend)
# ============================================================
router.register_group("reports", "monthly-waste-comparison", MonthlyWasteComparisonReportViewSet, basename="reports-monthly-waste-comparison")
router.register_group("reports", "daily-waste-comparisons", DailyWasteComparisonViewSet, basename="reports-daily-waste-comparisons")

# ============================================================
# GROUP: AUDIT
# ============================================================
router.register_group("audits", "login-audit", LoginAuditViewSet)
router.register_group("audits", "common-audit", CommonAuditViewSet)

# ============================================================
# GROUP: EXTERNAL ATTENDANCE
# ============================================================
router.register_group(
    "attendance",
    "external-records",
    ExternalAttendanceViewSet,
    basename="external-attendance",
)

# ============================================================
# GROUP: LOCALBODY (panchayat leader portal — auth-only, no module permission check)
# ============================================================
router.register_group("localbody", "dashboard", LocalBodyDashboardViewSet, basename="localbody-dashboard")

# ============================================================
# GROUP: DISTRICTBODY (district leader portal — auth-only, no module permission check)
# ============================================================
router.register_group("districtbody", "dashboard", DistrictBodyDashboardViewSet, basename="districtbody-dashboard")

# ============================================================
# GROUP: STATEBODY (state leader portal — auth-only, no module permission check)
# ============================================================
router.register_group("statebody", "dashboard", StateBodyDashboardViewSet, basename="statebody-dashboard")
router.register_group("statebody", "monthly-waste-comparison", StateMonthlyWasteComparisonViewSet, basename="statebody-monthly-waste-comparison")
router.register_group("statebody", "daily-waste-comparison", StateDailyWasteComparisonViewSet, basename="statebody-daily-waste-comparison")

# ============================================================
# GROUP: OPERATOR MOBILE
# ============================================================
router.register_group(
    "operator-mobile",
    "my-trip-today",
    MyTripTodayViewSet,
    basename="operator-mobile-my-trip-today",
)
router.register_group(
    "operator-mobile",
    "my-trips-today",
    MyTripsTodayViewSet,
    basename="operator-mobile-my-trips-today",
)
router.register_group(
    "operator-mobile",
    "validate-bin-qr",
    ValidateBinQrViewSet,
    basename="operator-mobile-validate-bin-qr",
)
router.register_group(
    "operator-mobile",
    "scan-bin",
    ScanBinViewSet,
    basename="operator-mobile-scan-bin",
)
router.register_group(
    "operator-mobile",
    "trip-history",
    TripHistoryViewSet,
    basename="operator-mobile-trip-history",
)

# ============================================================
# GROUP: WASTE BLUETOOTH
# ============================================================
router.register_group("waste-bluetooth", "types", WasteTypeViewSet)
router.register_group("waste-bluetooth", "collection-sub", WasteCollectionSubViewSet)
router.register_group("waste-bluetooth", "collection-main", WasteCollectionMainViewSet)


# ============================================================
# GROUP: MOBILE URLS
# ============================================================
router.register_group(
    "mobile",
    "login",
    DesktopLoginViewSet,
    basename="mobile-login",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "register",
    RegisterViewSet,
    basename="mobile-register",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "recognize",
    RecognizeViewSet,
    basename="mobile-recognize",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "employee",
    EmployeeViewSet,
    basename="mobile-employee",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "staff-profile",
    StaffProfileViewSet,
    basename="mobile-staff-profile",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "waste",
    WasteCollectionBluetoothViewSet,
    basename="mobile-waste-collection",
    include_group_in_prefix=False,
)
router.register_group(
    "mobile",
    "attendance-list",
    AttendanceListViewSet,
    basename="mobile-attendance-list",
    include_group_in_prefix=False,
)

# ============================================================
# URLS
# ============================================================
urlpatterns = [
    # Password reset flow (public — no authentication required)
    path("auth/forgot-password/", ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("auth/verify-otp/", VerifyOTPView.as_view(), name="auth-verify-otp"),
    path("auth/reset-password/", ResetPasswordView.as_view(), name="auth-reset-password"),
    # Authenticated password change (self-service and admin)
    path("auth/change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
    path("auth/admin-change-password/", AdminChangePasswordView.as_view(), name="auth-admin-change-password"),

    path(
        "permissions/userscreen/<str:userscreen_id>/columns/",
        UserScreenColumnsAPIView.as_view(),
    ),
    path("permissions/assign/", PermissionAssignAPIView.as_view()),
    path("permissions/user-screen/", UserPermissionsAPIView.as_view()),
    path("", include(router.urls)),
]

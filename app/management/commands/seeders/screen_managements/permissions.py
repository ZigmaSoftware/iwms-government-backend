from app.management.commands.seeders.base import BaseSeeder
from app.models.screen_managements.mainscreentype import MainScreenType
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen


USER_SCREEN_MODELS = {
    "continents": ("app", "Continent"),
    "countries": ("app", "Country"),
    "states": ("app", "State"),
    "districts": ("app", "District"),
    "area-types": ("app", "AreaType"),
    "corporations": ("app", "Corporation"),
    "municipalities": ("app", "Municipality"),
    "town-panchayats": ("app", "TownPanchayat"),
    "panchayat-unions": ("app", "PanchayatUnion"),
    "panchayats": ("app", "Panchayat"),
    "properties": ("app", "Property"),
    "subproperties": ("app", "SubProperty"),
    "bins": ("app", "Bins"),
    "wastetypes": ("app", "WasteType"),
    "mainscreentype": ("app", "MainScreenType"),
    "mainscreens": ("app", "MainScreen"),
    "userscreens": ("app", "UserScreen"),
    "userscreen-action": ("app", "UserScreenAction"),
    "userscreenpermissions": ("app", "UserScreenPermission"),
    "user-type": ("app", "UserType"),
    "staff-user-type": ("app", "StaffUserType"),
    "staffcreation": ("app", "StaffcreationOfficeDetails"),
    "staff-access-configuration": ("app", "StaffcreationOfficeDetails"),
    "customercreations": ("app", "CustomerCreation"),
    "feedbacks": ("app", "FeedBack"),
    "tickets": ("app", "ComplaintTicket"),
    "modules": ("app", "ComplaintModule"),
    "categories": ("app", "ComplaintCategory"),
    "subcategories": ("app", "ComplaintSubcategory"),
    "priorities": ("app", "ComplaintPriority"),
    "statuses": ("app", "ComplaintStatus"),
    "sources": ("app", "ComplaintSource"),
    "teams": ("app", "ComplaintTeam"),
    "sla-rules": ("app", "ComplaintSlaRule"),
    "feedback": ("app", "ComplaintFeedback"),
    "vehicle-type": ("app", "VehicleTypeCreation"),
    "vehicle-creation": ("app", "VehicleCreation"),
    "fuels": ("app", "Fuel"),
    "staff-templates": ("app", "StaffTemplate"),
    "alternative-staff-templates": ("app", "AlternativeStaffTemplate"),
    "collection-points": ("app", "Collection_point"),
    "trip-plans": ("app", "TripPlan"),
    "daily-trip-assignments": ("app", "DailyTripAssignment"),
    "daily-trip-collection-points": ("app", "DailyTripCollectionPoint"),
    "daily-trip-household-collections": ("app", "DailyTripHouseholdCollection"),
    "bin-collection-events": ("app", "BinCollectionEvent"),
    "vehicle-breakdowns": ("app", "VehicleBreakdown"),
    "daily-trip-logs": ("app", "DailyTripLog"),
    "wastecollections": ("app", "WasteCollection"),
    "daily-waste-comparisons": ("app", "DailyWasteComparison"),
    "MonthlyWasteComparison": ("app", "MonthlyWeightReport"),
    "common-audit": ("app", "StaffTemplateAuditLog"),
    "login-audit": ("app", "LoginAudit"),
    "plb-leader-creation": ("app", "PanchayatLeaderLogin"),
    "district-leader-creation": ("app", "DistrictLeaderLogin"),
}


class PermissionSeeder(BaseSeeder):
    name = "PermissionSeeder"

    def _get_unique_value(self, model_class, field_name, preferred_value, exclude_pk=None):
        if not preferred_value:
            preferred_value = "screen"

        candidate = preferred_value
        counter = 2
        while model_class.objects.filter(**{field_name: candidate}).exclude(pk=exclude_pk).exists():
            candidate = f"{preferred_value}-{counter}"
            counter += 1

        return candidate

    def _get_or_create_main_screen(self, mainscreentype, name, order_no, icon_name, description):
        existing = MainScreen.objects.filter(mainscreen_name=name).first()
        icon_name = self._get_unique_value(
            MainScreen,
            "icon_name",
            icon_name,
            exclude_pk=existing.pk if existing else None,
        )

        return MainScreen.objects.update_or_create(
            mainscreen_name=name,
            defaults={
                "mainscreentype_id": mainscreentype,
                "icon_name": icon_name,
                "order_no": order_no,
                "description": description,
                "is_active": True,
                "is_deleted": False,
            },
        )

    def _get_or_create_user_screen(
        self,
        main_screen,
        userscreen_name,
        order_no,
        folder_name,
        icon_name,
        description,
    ):
        model_app_label, model_name = USER_SCREEN_MODELS.get(userscreen_name, (None, None))
        existing = UserScreen.objects.filter(userscreen_name=userscreen_name).first()
        folder_name = self._get_unique_value(
            UserScreen,
            "folder_name",
            folder_name,
            exclude_pk=existing.pk if existing else None,
        )
        icon_name = self._get_unique_value(
            UserScreen,
            "icon_name",
            icon_name,
            exclude_pk=existing.pk if existing else None,
        )

        return UserScreen.objects.update_or_create(
            userscreen_name=userscreen_name,
            defaults={
                "mainscreen_id": main_screen,
                "folder_name": folder_name,
                "icon_name": icon_name,
                "order_no": order_no,
                "description": description,
                "model_app_label": model_app_label,
                "model_name": model_name,
                "is_active": True,
                "is_deleted": False,
            },
        )

    def _move_mainscreen_orders_out_of_range(self, mainscreentype, reserved_count):
        screens = list(
            MainScreen.objects.filter(mainscreentype_id=mainscreentype)
            .order_by("order_no", "unique_id")
        )
        if not screens:
            return

        max_order = max((screen.order_no or 0) for screen in screens)
        offset = max_order + len(screens) + reserved_count + 1000
        for idx, screen in enumerate(screens, start=1):
            screen.order_no = offset + idx
            screen.save(update_fields=["order_no"])

    def _move_userscreen_orders_out_of_range(self, main_screen, reserved_count):
        screens = list(
            UserScreen.objects.filter(mainscreen_id=main_screen)
            .order_by("order_no", "unique_id")
        )
        if not screens:
            return

        max_order = max((screen.order_no or 0) for screen in screens)
        offset = max_order + len(screens) + reserved_count + 1000
        for idx, screen in enumerate(screens, start=1):
            screen.order_no = offset + idx
            screen.save(update_fields=["order_no"])

    def _deactivate_removed_sidebar_screens(
        self,
        mainscreentype,
        active_modules,
        active_user_screens,
    ):
        stale_user_screens = UserScreen.objects.filter(
            mainscreen_id__mainscreentype_id=mainscreentype,
        ).exclude(userscreen_name__in=active_user_screens)
        stale_userscreen_count = stale_user_screens.update(is_active=False, is_deleted=True)

        stale_main_screens = MainScreen.objects.filter(
            mainscreentype_id=mainscreentype,
        ).exclude(mainscreen_name__in=active_modules)
        stale_mainscreen_count = stale_main_screens.update(is_active=False, is_deleted=True)

        if stale_mainscreen_count or stale_userscreen_count:
            self.log(
                "Soft-disabled "
                f"{stale_mainscreen_count} stale main screens and "
                f"{stale_userscreen_count} stale user screens not present in AppSidebar."
            )

    def run(self):
        megamenu, _ = MainScreenType.objects.get_or_create(
            type_name="megamenu",
            defaults={
                "is_active": True,
                "is_deleted": False,
            },
        )

        sidebar_modules = [
            {
                "module": "dashboard",
                "icon": "dashboard",
                "order": 1,
                "description": "Dashboard landing page",
                "subitems": [("Dashboard", "Dashboard", "dashboard", 1, "Dashboard")],
            },
            {
                "module": "common-masters",
                "icon": "layers",
                "order": 2,
                "description": "Common geographic master data",
                "subitems": [
                    ("continents", "continents", "continents", 1, "Continents"),
                    ("countries", "countries", "countries", 2, "Countries"),
                    ("states", "states", "states", 3, "States"),
                ],
            },
            {
                "module": "masters",
                "icon": "layers",
                "order": 3,
                "description": "Administrative and local-body master data",
                "subitems": [
                    ("districts", "districts", "districts", 1, "Districts"),
                    ("area-types", "area-types", "area-types", 2, "Area types"),
                    ("corporations", "corporations", "corporations", 3, "Corporations"),
                    ("municipalities", "municipalities", "municipalities", 4, "Municipalities"),
                    ("town-panchayats", "town-panchayats", "town-panchayats", 5, "Town panchayats"),
                    ("panchayat-unions", "panchayat-unions", "panchayat-unions", 6, "Panchayat unions"),
                    ("panchayats", "panchayats", "panchayats", 7, "Panchayats"),
                ],
            },
            {
                "module": "waste-types",
                "icon": "recycling",
                "order": 4,
                "description": "Waste type configuration",
                "subitems": [
                    ("properties", "properties", "properties", 1, "Property definitions"),
                    ("subproperties", "subproperties", "subproperties", 2, "Sub-property definitions"),
                ],
            },
            {
                "module": "assets",
                "icon": "inventory_2",
                "order": 5,
                "description": "Asset and waste handling screens",
                "subitems": [
                    ("bins", "bins", "bins", 1, "Bin creation"),
                    ("wastetypes", "wastetypes", "wastetypes", 2, "Waste type maintenance"),
                ],
            },
            {
                "module": "screen-managements",
                "icon": "settings",
                "order": 6,
                "description": "Screen setup and permission management",
                "subitems": [
                    ("mainscreentype", "mainscreentype", "mainscreentype", 1, "Main screen types"),
                    ("mainscreens", "mainscreens", "mainscreens", 2, "Main screens"),
                    ("userscreens", "userscreens", "userscreens", 3, "User screens"),
                    ("userscreen-action", "userscreen-action", "userscreen-action", 4, "User screen actions"),
                    ("userscreenpermissions", "userscreenpermissions", "userscreenpermissions", 5, "User screen permissions"),
                ],
            },
            {
                "module": "role-assigns",
                "icon": "admin_panel_settings",
                "order": 7,
                "description": "Role assignment configuration",
                "subitems": [
                    ("user-type", "user-type", "user-type", 1, "User types"),
                    ("staff-user-type", "staff-user-type", "staff-user-type", 2, "Staff user types"),
                ],
            },
            {
                "module": "user-creations",
                "icon": "group_add",
                "order": 8,
                "description": "User and staff creation",
                "subitems": [
                    ("staffcreation", "staffcreation", "staffcreation", 1, "Staff creation"),
                    (
                        "staff-access-configuration",
                        "staff-access-configuration",
                        "staff-access-configuration",
                        2,
                        "Staff access configuration",
                    ),
                ],
            },
            {
                "module": "customers",
                "icon": "groups",
                "order": 9,
                "description": "Customer master screens",
                "subitems": [
                    ("customercreations", "customercreations", "customercreations", 1, "Customer creation"),
                    ("feedbacks", "feedbacks", "feedbacks", 2, "Feedback"),
                ],
            },
            {
                "module": "complaint-ticket",
                "icon": "support_agent",
                "order": 10,
                "description": "Complaint ticket management",
                "subitems": [
                    ("tickets", "tickets", "tickets", 1, "Complaint tickets"),
                    ("modules", "modules", "modules", 2, "Modules"),
                    ("categories", "categories", "categories", 3, "Categories"),
                    ("subcategories", "subcategories", "subcategories", 4, "Subcategories"),
                    ("priorities", "priorities", "priorities", 5, "Priorities"),
                    ("statuses", "statuses", "statuses", 6, "Statuses"),
                    ("sources", "sources", "sources", 7, "Sources"),
                    ("teams", "teams", "teams", 8, "Teams"),
                    ("sla-rules", "sla-rules", "sla-rules", 9, "SLA rules"),
                    ("feedback", "feedback", "feedback", 10, "Feedback"),
                ],
            },
            {
                "module": "transport-masters",
                "icon": "local_shipping",
                "order": 11,
                "description": "Transport and vehicle setup",
                "subitems": [
                    ("vehicle-type", "vehicle-type", "vehicle-type", 1, "Vehicle type"),
                    ("vehicle-creation", "vehicle-creation", "vehicle-creation", 2, "Vehicle creation"),
                    ("fuels", "fuels", "fuels", 3, "Fuels"),
                ],
            },
            {
                "module": "schedule-masters",
                "icon": "event_note",
                "order": 12,
                "description": "Schedule planning, operations, and reports",
                "subitems": [
                    ("staff-templates", "staff-templates", "staff-templates", 1, "Staff templates"),
                    ("alternative-staff-templates", "alternative-staff-templates", "alternative-staff-templates", 2, "Alternative staff templates"),
                    ("collection-points", "collection-points", "collection-points", 3, "Collection points"),
                    ("trip-plans", "trip-plans", "trip-plans", 4, "Trip plans"),
                    ("daily-trip-assignments", "daily-trip-assignments", "daily-trip-assignments", 5, "Daily trip assignments"),
                    ("daily-trip-collection-points", "daily-trip-collection-points", "daily-trip-collection-points", 6, "Daily trip collection points"),
                    ("daily-trip-household-collections", "daily-trip-household-collections", "daily-trip-household-collections", 7, "Daily trip household collections"),
                    ("bin-collection-events", "bin-collection-events", "bin-collection-events", 8, "Bin collection events"),
                    ("vehicle-breakdowns", "vehicle-breakdowns", "vehicle-breakdowns", 9, "Vehicle breakdowns"),
                    ("daily-trip-logs", "daily-trip-logs", "daily-trip-logs", 10, "Daily trip logs"),
                    ("wastecollections", "wastecollections", "wastecollections", 11, "Waste collected data"),
                    ("daily-waste-comparisons", "daily-waste-comparisons", "daily-waste-comparisons", 12, "Daily waste comparisons"),
                    ("MonthlyWasteComparison", "MonthlyWasteComparison", "MonthlyWasteComparison", 13, "Monthly waste comparison"),
                ],
            },
            {
                "module": "audits",
                "icon": "fact_check",
                "order": 13,
                "description": "Audit and activity logs",
                "subitems": [
                    ("common-audit", "common-audit", "common-audit", 1, "Common audit"),
                    ("login-audit", "login-audit", "login-audit", 2, "Login audit"),
                ],
            },
            {
                "module": "vehicle-tracking",
                "icon": "local_shipping",
                "order": 14,
                "description": "Vehicle tracking and history",
                "subitems": [
                    ("VehicleTrack", "VehicleTrack", "VehicleTrack", 1, "Vehicle tracking"),
                    ("VehicleHistory", "VehicleHistory", "VehicleHistory", 2, "Vehicle history"),
                ],
            },
            {
                "module": "reports",
                "icon": "bar_chart",
                "order": 15,
                "description": "Fleet and waste reports",
                "subitems": [
                    ("TripSummary", "TripSummary", "TripSummary", 1, "Trip summary"),
                    ("MonthlyDistance", "MonthlyDistance", "MonthlyDistance", 2, "Monthly distance"),
                    ("WasteCollectedSummary", "WasteCollectedSummary", "WasteCollectedSummary", 3, "Waste collected summary"),
                ],
            },
            {
                "module": "workforce",
                "icon": "group",
                "order": 16,
                "description": "Workforce management",
                "subitems": [
                    ("WorkforceManagement", "WorkforceManagement", "WorkforceManagement", 1, "Workforce management"),
                ],
            },
            {
                "module": "leader-login",
                "icon": "badge",
                "order": 17,
                "description": "Leader login management",
                "subitems": [
                    ("plb-leader-creation", "plb-leader-creation", "plb-leader-creation", 1, "PLB leader creation"),
                    ("district-leader-creation", "district-leader-creation", "district-leader-creation", 2, "District leader creation"),
                ],
            },
        ]

        self._move_mainscreen_orders_out_of_range(megamenu, len(sidebar_modules))

        main_screens = {}
        created_main_screens = 0
        created_user_screens = 0
        active_modules = {section["module"] for section in sidebar_modules}
        active_user_screens = {
            subitem[0]
            for section in sidebar_modules
            for subitem in section.get("subitems", [])
        }

        for section in sidebar_modules:
            main_screen, created = self._get_or_create_main_screen(
                megamenu,
                section["module"],
                section["order"],
                section["icon"],
                section["description"],
            )
            main_screens[section["module"]] = main_screen
            if created:
                created_main_screens += 1

            self._move_userscreen_orders_out_of_range(main_screen, len(section.get("subitems", [])))

            for index, subitem in enumerate(section.get("subitems", []), start=1):
                userscreen_name, folder_name, icon_name, order_no, description = subitem
                _, created = self._get_or_create_user_screen(
                    main_screen,
                    userscreen_name,
                    order_no or index,
                    folder_name,
                    icon_name,
                    description,
                )
                if created:
                    created_user_screens += 1

        self._deactivate_removed_sidebar_screens(
            megamenu,
            active_modules,
            active_user_screens,
        )

        self.log(
            f"Sidebar-based permission screens seeded: {created_main_screens} main screens and {created_user_screens} user screens."
        )

from django.db.models import F

from app.management.commands.seeders.base import BaseSeeder
from app.models.screen_managements.mainscreentype import MainScreenType
from app.models.screen_managements.userscreenaction import UserScreenAction
from app.models.screen_managements.mainscreen import MainScreen
from app.models.screen_managements.userscreen import UserScreen
from app.models.screen_managements.companyuserscreenpermission import (
    CompanyUserScreenPermission,
)
from app.models.role_assigns.userType import UserType
from app.models.role_assigns.staffUserType import StaffUserType
from app.models.superadmin_masters.company import Company

from app.models.screen_managements.userscreencolumn import UserScreenColumn
from app.models.screen_managements.companyuserscreencolumnpermission import (
    CompanyUserScreenColumnPermission,
)


class PermissionSeeder(BaseSeeder):
    name = "permission_full"

    def run(self):
        # --------------------------------------------------
        # 0. COMPANIES
        # --------------------------------------------------
        companies = Company.objects.filter(is_deleted=False)
        if not companies.exists():
            self.log("No companies found. Seed companies first.")
            return

        # --------------------------------------------------
        # 1. MAIN SCREEN TYPE
        # --------------------------------------------------
        megamenu, _ = MainScreenType.objects.get_or_create(
            type_name="megamenu",
            defaults={
                "is_active": True,
                "is_deleted": False,
            },
        )

        # --------------------------------------------------
        # 2. ACTIONS
        # --------------------------------------------------
        actions = {}
        for name in ["add", "view", "edit", "delete", "show"]:
            action, _ = UserScreenAction.objects.get_or_create(
                action_name=name,
                defaults={
                    "variable_name": name,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            actions[name] = action

        # --------------------------------------------------
        # 3. SCREEN STRUCTURE (MATCHES ROUTER GROUPS)
        # --------------------------------------------------
        screen_structure = {
            "common-masters": [
                "continents",
                "countries",
                "states",
            ],
            "masters": [
                "districts",
                "cities",
                "zones",
                "wards",
                "panchayat",
                "area type",
                "department-masters",
                "designation-masters",
                "panchayat-leaders",
            ],
            "waste-types": [
                "properties",
                "subproperties",
            ],
            "assets": [
                "bins",
                # "collection point",
                "waste type",
            ],
            "screen-managements": [
                "mainscreentype",
                "mainscreens",
                "userscreens",
                "userscreen-action",
                "CompanyUserScreenPermission",
            ],
            "role-assigns": [
                "user-type",
                "staffusertypes",
                "contractorusertypes",
            ],
            "user-creations": [
                # "users-creation",
                "staffcreation",
                # "stafftemplate-creation",
                # "alternative-stafftemplate",
                # "supervisor-zone-map",
                # "unassigned-staff-pool",
            ],
            "process": [
                "zone-property-load-tracker",
            ],
            "customers": [
                "customercreations",
                "apartment-list",
                "wastecollections",
                "feedbacks",
                # "user-charge-rules",
            ],
            # "waste-management": [
            #     "collection monitoring",
            #     "panchayat base collection",
            #     "ward base collection",
            # ],
            "grivences": [
                "complaints",
                "main-category",
                "sub-category",
            ],
            "transport-masters": [
                "vehicle-type",
                "vehicle-creation",
                # "trip-attendance",
                "fuels",
            ],
            "schedule-masters": [
                "staff-templates",
                "alternative-staff-templates",
                "collection-points",
                "trip-plans",
                "trip-plan-collection-points",
                "daily-trip-assignments",
                "daily-trip-collection-points",
                "daily-trip-household-collections",
                "bin-collection-events",
                "daily-trip-logs",
                "monthly-waste-comparison",
            ],
            "audits": [
                # "stafftemplate-audit-log",
                # "supervisor-zone-access-audit",
                # "vehicle-trip-audit",
                # "trip-exception-log",
                # "bin-load-log",
                "common-audit"
            ],
            "reports": [
                "trip-summary",
                "monthly-distance",
                "waste-collected-summary",
                # "monthly-waste-comparison",
            ],
        }

        # --------------------------------------------------
        # 4. CREATE MAIN SCREENS + USER SCREENS
        # --------------------------------------------------
        mainscreens = {}

        total_mains = len(screen_structure)
        if total_mains:
            MainScreen.objects.filter(order_no__lte=total_mains).update(
                order_no=F("order_no") + total_mains
            )

        for order, (main_name, screens) in enumerate(screen_structure.items(), start=1):
            main, _ = MainScreen.objects.update_or_create(
                mainscreen_name=main_name,
                defaults={
                    "mainscreentype_id": megamenu,
                    "icon_name": main_name,
                    "order_no": order,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            mainscreens[main_name] = main

            UserScreen.objects.filter(mainscreen_id=main).update(
                order_no=F("order_no") + 1000
            )

            ordered_screens = []
            for idx, screen_name in enumerate(screens, start=1):
                screen, _ = UserScreen.objects.get_or_create(
                    userscreen_name=screen_name,
                    defaults={
                        "mainscreen_id": main,
                        "folder_name": screen_name,
                        "icon_name": screen_name,
                        "order_no": idx,
                        "is_active": True,
                        "is_deleted": False,
                    },
                )
                ordered_screens.append(screen)

            for idx, screen in enumerate(ordered_screens, start=1):
                screen.order_no = idx
                screen.is_active = True
                screen.is_deleted = False
                screen.save(update_fields=["order_no", "is_active", "is_deleted"])

                # Persist model mapping for known screens so schema resolver can find models
                mapping = {
                    "department-masters": ("app", "Department"),
                    "designation-masters": ("app", "Designation"),
                    "panchayat-leaders": ("app", "PanchayatLeaderLogin"),
                }
                if screen.userscreen_name in mapping:
                    app_label, model_name = mapping[screen.userscreen_name]
                    if screen.model_app_label != app_label or screen.model_name != model_name:
                        screen.model_app_label = app_label
                        screen.model_name = model_name
                        screen.save(update_fields=["model_app_label", "model_name", "updated_at"])

    

     
        # --------------------------------------------------
        # 4C. MONTHLY WASTE COMPARISON COLUMNS
        # --------------------------------------------------
        reports_main = mainscreens.get("reports")
        if reports_main:
            monthly_waste_screen = UserScreen.objects.filter(
                mainscreen_id=reports_main,
                userscreen_name="monthly-waste-comparison",
                is_deleted=False,
            ).first()
            if monthly_waste_screen:
                monthly_waste_columns = [
                    ("month",                         "Month",                   "string",  "month",                          1),
                    ("panchayat_name",                "Panchayat",               "string",  "panchayat_id__panchayat_name",   2),
                    ("waste_type",                    "Waste Type",              "string",  "waste_type_id__waste_type_name",  3),
                    ("total_agreed_weight",           "Agreed Weight (kg)",      "decimal", "agreed_weight_kg",               4),
                    ("total_actual_weight",           "Actual Weight (kg)",      "decimal", "actual_weight_kg",               5),
                    ("variance_kg",                   "Variance (kg)",           "decimal", "variance_kg",                    6),
                    ("variance_percent",              "Variance %",              "decimal", "variance_percent",               7),
                    ("report_status",                 "Status",                  "string",  "report_status",                  8),
                    ("total_trips",                   "Total Trips",             "integer", "total_trips",                    9),
                    ("collection_points_covered",     "Collection Points",       "integer", "collection_points_covered",      10),
                    ("collection_efficiency_percent", "Collection Efficiency %", "decimal", "collection_efficiency_percent",  11),
                    ("average_weight_per_trip",       "Avg Weight/Trip (kg)",    "decimal", "average_weight_per_trip",        12),
                    ("coverage_efficiency_percent",   "Coverage Efficiency %",   "decimal", "coverage_efficiency_percent",    13),
                ]
                for field_name, display_name, data_type, db_col, order_no in monthly_waste_columns:
                    UserScreenColumn.objects.update_or_create(
                        userscreen_id=monthly_waste_screen,
                        field_name=field_name,
                        is_deleted=False,
                        defaults={
                            "display_name": display_name,
                            "data_type": data_type,
                            "db_column": db_col,
                            "order_no": order_no,
                            "is_required": False,
                            "is_nullable": True,
                            "is_active": True,
                            "is_visible": True,
                            "is_editable": False,
                            "is_filterable": True,
                            "is_searchable": True,
                            "is_sortable": True,
                        },
                    )
                self.log("Monthly waste comparison columns seeded.")

        # --------------------------------------------------
        # 4D. PANCHAYAT COLUMNS
        # --------------------------------------------------
        masters_main = mainscreens.get("masters")
        if masters_main:
            panchayat_screen = UserScreen.objects.filter(
                mainscreen_id=masters_main,
                userscreen_name="panchayat",
                is_deleted=False,
            ).first()
            if panchayat_screen:
                panchayat_columns = [
                    ("agreed_weight_kg", "Agreed Weight", "decimal", "agreed_weight_kg", 50),
                    ("weight_unit",      "Weight Unit",   "string",  "weight_unit",      51),
                    ("effective_from",   "Effective From","date",    "effective_from",   52),
                ]
                for field_name, display_name, data_type, db_column, order_no in panchayat_columns:
                    UserScreenColumn.objects.update_or_create(
                        userscreen_id=panchayat_screen,
                        field_name=field_name,
                        is_deleted=False,
                        defaults={
                            "display_name": display_name,
                            "data_type": data_type,
                            "db_column": db_column,
                            "order_no": order_no,
                            "is_required": False,
                            "is_nullable": True,
                            "is_active": True,
                            "is_visible": True,
                            "is_editable": True,
                            "is_filterable": True,
                            "is_searchable": True,
                            "is_sortable": True,
                        },
                    )

        # --------------------------------------------------
        # 5. SUPERADMIN ROLE LOOKUP
        # --------------------------------------------------
        platform_type = UserType.objects.filter(name__iexact="platform").first()
        superadmin_role = None
        if platform_type:
            superadmin_role = StaffUserType.objects.filter(
                usertype_id=platform_type,
                name__iexact="superadmin",
            ).first()

        if not platform_type or not superadmin_role:
            self.log("SuperAdmin role not found. Seed userType and staffUserType first.")
            return

        # --------------------------------------------------
        # 6. SUPERADMIN SCREEN PERMISSIONS (FULL ACCESS TO ALL SCREENS)
        # --------------------------------------------------
        for company in companies:
            self.log(f"--- Seeding superadmin permissions for company: {company.name} ---")

            for main in mainscreens.values():
                for screen in UserScreen.objects.filter(mainscreen_id=main, is_deleted=False):
                    for order_no, action in enumerate(actions.values(), start=1):
                        CompanyUserScreenPermission.objects.get_or_create(
                            company_id=company,
                            usertype_id=platform_type,
                            staffusertype_id=superadmin_role,
                            mainscreen_id=main,
                            userscreen_id=screen,
                            userscreenaction_id=action,
                            defaults={
                                "order_no": order_no,
                                "description": f"{action.variable_name} {screen.userscreen_name}",
                                "is_active": True,
                                "is_deleted": False,
                            },
                        )

        # --------------------------------------------------
        # 7. SUPERADMIN COLUMN PERMISSIONS (FULL ACCESS TO ALL COLUMNS)
        # --------------------------------------------------
        self.log("Seeding superadmin column permissions...")

        all_screens = UserScreen.objects.filter(is_deleted=False, is_active=True)

        for company in companies:
            for screen in all_screens:
                columns = UserScreenColumn.objects.filter(
                    userscreen_id=screen,
                    is_deleted=False,
                    is_active=True,
                )
                for order_no, column in enumerate(columns, start=1):
                    CompanyUserScreenColumnPermission.objects.update_or_create(
                        company_id=company,
                        project_id=None,
                        usertype_id=platform_type,
                        staffusertype_id=superadmin_role,
                        contractorusertype_id=None,
                        userscreen_id=screen,
                        column_id=column,
                        defaults={
                            "can_view": True,
                            "order_no": order_no,
                            "description": f"{screen.userscreen_name} - {column.display_name}",
                            "is_active": True,
                            "is_deleted": False,
                        },
                    )

        self.log("--- SuperAdmin permission seeding completed successfully ---")

from app.management.commands.seeders.base import BaseSeeder
from app.models.screen_managements.mainscreentype import MainScreenType
from app.models.screen_managements.mainscreen import MainScreen


class PermissionSeeder(BaseSeeder):
    name = "PermissionSeeder"

    SCREEN_TYPES = [
        "Dashboard",
        "Masters",
        "Schedule",
        "Schedule Setup",
        "Schedule Operations",
        "Schedule Reports",
        "Reports",
        "Settings",
    ]

    # (type_name, screen_name, icon_name, order_no, description)
    SCREENS = [
        # Dashboard
        ("Dashboard", "Home Dashboard", "home", 1, "Main dashboard overview"),

        # Masters
        ("Masters", "Staff Management", "people", 1, "Manage staff records"),

        # Schedule Setup
        ("Schedule Setup", "Staff Templates",             "group",         1, "Manage staff team templates"),
        ("Schedule Setup", "Alternative Staff Templates", "swap_horiz",    2, "Manage alternative staff templates"),
        ("Schedule Setup", "Collection Points",           "place",         3, "Manage secondary collection points"),
        ("Schedule Setup", "Trip Plans",                  "route",         4, "Create and manage trip plans"),
        ("Schedule Setup", "Trip Plan Collection Points", "pin_drop",      5, "Manage stops per trip plan"),

        # Schedule Operations
        ("Schedule Operations", "Daily Trip Assignment",          "event",          1, "Assign daily trips to staff"),
        ("Schedule Operations", "Daily Trip Collection Point",    "location_on",    2, "Track daily collection point visits"),
        ("Schedule Operations", "Daily Trip Household Collection","home",           3, "Household-level daily waste collection"),
        ("Schedule Operations", "Daily Trip Tracking",            "track_changes",  4, "Live tracking of daily trips"),
        ("Schedule Operations", "Bin Collection Event",           "recycling",      5, "Secondary bin pickup events"),
        ("Schedule Operations", "Daily Trip Log",                 "list_alt",       6, "Daily trip execution logs"),

        # Schedule Reports
        ("Schedule Reports", "Daily Waste Comparison",   "bar_chart",   1, "Compare daily waste collected vs target"),
        ("Schedule Reports", "Monthly Waste Comparison", "analytics",   2, "Monthly aggregated waste report"),

        # Reports
        ("Reports", "Waste Reports", "bar_chart", 1, "View waste collection reports"),

        # Settings
        ("Settings", "System Settings", "settings", 1, "Application settings"),
    ]

    def run(self):
        type_cache = {}
        for type_name in self.SCREEN_TYPES:
            obj, _ = MainScreenType.objects.get_or_create(
                type_name=type_name,
                defaults={"is_active": True, "is_deleted": False},
            )
            type_cache[type_name] = obj

        count = 0
        for type_name, screen_name, icon_name, order_no, description in self.SCREENS:
            screen_type = type_cache.get(type_name)
            if not screen_type:
                continue

            _, created = MainScreen.objects.get_or_create(
                mainscreen_name=screen_name,
                defaults={
                    "mainscreentype_id": screen_type,
                    "icon_name": icon_name,
                    "order_no": order_no,
                    "description": description,
                    "is_active": True,
                    "is_deleted": False,
                },
            )
            if created:
                count += 1

        self.log(f"---Screen permissions seeded ({count} screens created)---")

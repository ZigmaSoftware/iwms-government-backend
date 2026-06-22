from app.management.commands.seeders.base import BaseSeeder
from app.models.screen_managements.mainscreentype import MainScreenType
from app.models.screen_managements.mainscreen import MainScreen


class PermissionSeeder(BaseSeeder):
    name = "PermissionSeeder"

    # (type_name) — 5 screen types
    SCREEN_TYPES = [
        "Dashboard",
        "Masters",
        "Schedule",
        "Reports",
        "Settings",
    ]

    # (screen_type_name, screen_name, icon_name, order_no, description)
    SCREENS = [
        ("Dashboard", "Home Dashboard",       "home",     1, "Main dashboard overview"),
        ("Masters",   "Staff Management",     "people",   1, "Manage staff records"),
        ("Schedule",  "Trip Management",      "route",    1, "Manage trip schedules"),
        ("Reports",   "Waste Reports",        "bar_chart",1, "View waste collection reports"),
        ("Settings",  "System Settings",      "settings", 1, "Application settings"),
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

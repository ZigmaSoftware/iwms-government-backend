"""Configure existing mobile users so their app access works.

App access is granted by ticking an App Module on a StaffAccessConfiguration.
Nobody has one yet, so every driver/operator/supervisor would be refused at the
mobile login. This backfills them once: it creates their configuration, ticks
the App Module for their role, and grants the screens that role's app actually
calls (ROLE_SCREEN_TEMPLATES).

    python manage.py backfill_app_access                 # show what it would do
    python manage.py backfill_app_access --apply
    python manage.py backfill_app_access --apply --username supervisor_user

Users who already have a configuration are left alone unless --overwrite is
given, so this is safe to re-run.
"""

from django.core.cache import cache
from django.core.management.base import BaseCommand

from app.models.masters.customer_masters.customer_access_configuration import (
    CustomerAccessConfiguration,
)
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfiguration,
    StaffAccessConfigurationPermission,
)
from app.models.superadmin.staff_management.staffcreation import (
    StaffcreationOfficeDetails,
)
from app.utils.app_feature_grants import (
    CITIZEN_APP_SCREENS,
    ROLE_SCREEN_TEMPLATES,
)

# Role keyword -> the app they sign into. Roles here are stored with a tenant
# prefix ("govt_panchayat_supervisor"), so match on the significant word.
ROLE_SURFACES = [
    ("supervisor", "supervisor"),
    ("operator", "operator"),
    ("driver", "driver"),
]


def surface_for_role(role_name):
    normalized = (role_name or "").strip().lower()
    for keyword, surface in ROLE_SURFACES:
        if keyword in normalized:
            return surface
    return None


def role_name_for(staff):
    for attr in ("staffusertype_id", "governmentusertype_id", "contractorusertype_id"):
        name = getattr(getattr(staff, attr, None), "name", None)
        if name:
            return name
    return None


class Command(BaseCommand):
    help = "Create access configurations for existing mobile app users."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Write the changes. Without it, only reports.")
        parser.add_argument("--username", help="Limit to one user.")
        parser.add_argument("--overwrite", action="store_true",
                            help="Also re-apply to users who already have a configuration.")

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        self.actions = {
            (row.variable_name or row.action_name or "").lower(): row
            for row in UserScreenAction.objects.filter(is_deleted=False)
        }
        self.modules = {
            module.surface_key: module
            for module in AppModule.objects.filter(is_active=True, is_deleted=False)
        }

        staff_done = self._backfill_staff(options, apply_changes)
        customers_done = self._backfill_customers(options, apply_changes)

        if apply_changes:
            cache.clear()
            self.stdout.write(self.style.SUCCESS(
                f"\nConfigured {staff_done} staff and {customers_done} customers."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"\nDRY RUN — {staff_done} staff and {customers_done} customers "
                "would be configured. Re-run with --apply."
            ))

    def _backfill_staff(self, options, apply_changes):
        queryset = StaffcreationOfficeDetails.objects.filter(
            is_deleted=False
        ).select_related(
            "staffusertype_id", "governmentusertype_id", "contractorusertype_id"
        )
        if options["username"]:
            queryset = queryset.filter(username=options["username"])

        done = 0
        for staff in queryset:
            surface = surface_for_role(role_name_for(staff))
            if not surface:
                continue

            existing = StaffAccessConfiguration.objects.filter(
                staff_id_id=staff.staff_unique_id, is_deleted=False
            ).first()
            if existing and not options["overwrite"]:
                self.stdout.write(f"  {staff.username:24} skipped (already configured)")
                continue

            screens = self._resolve_screens(ROLE_SCREEN_TEMPLATES.get(surface, {}))
            self.stdout.write(
                f"  {staff.username:24} {surface:11} {len(screens)} screens, module={surface}"
            )
            if not apply_changes:
                done += 1
                continue

            config = existing or StaffAccessConfiguration.objects.create(staff_id=staff)

            module = self.modules.get(surface)
            if module:
                config.app_modules.add(module)

            for order, (screen, action_names) in enumerate(screens, start=1):
                for name in action_names:
                    action = self.actions.get(name)
                    if not action:
                        continue
                    StaffAccessConfigurationPermission.objects.update_or_create(
                        staff_access_configuration_id=config,
                        mainscreen_id=screen.mainscreen_id,
                        userscreen_id=screen,
                        userscreenaction_id=action,
                        defaults={"order_no": order, "is_active": True, "is_deleted": False},
                    )

            if not staff.app_module:
                StaffcreationOfficeDetails.objects.filter(pk=staff.pk).update(
                    app_module=surface
                )
            done += 1

        return done

    def _backfill_customers(self, options, apply_changes):
        queryset = CustomerCreation.objects.filter(is_deleted=False, is_active=True)
        if options["username"]:
            queryset = queryset.filter(username=options["username"])
        queryset = queryset.exclude(username__isnull=True).exclude(username="")

        citizen_module = self.modules.get("citizen")
        citizen_screens = list(
            UserScreen.objects.filter(
                userscreen_name__in=CITIZEN_APP_SCREENS, is_deleted=False
            )
        )

        done = 0
        for customer in queryset:
            existing = CustomerAccessConfiguration.objects.filter(
                customer_id_id=customer.unique_id, is_deleted=False
            ).first()
            if existing and not options["overwrite"]:
                continue
            if not apply_changes:
                done += 1
                continue

            config = existing or CustomerAccessConfiguration.objects.create(
                customer_id=customer
            )
            if citizen_module:
                config.app_modules.add(citizen_module)
            if citizen_screens:
                config.app_screens.add(*citizen_screens)
            if not customer.app_module:
                CustomerCreation.objects.filter(pk=customer.pk).update(
                    app_module="citizen"
                )
            done += 1

        self.stdout.write(f"  customers: {done}")
        return done

    def _resolve_screens(self, template):
        """[(UserScreen, [action names])] for a role template."""
        wanted = {}
        for screens in template.values():
            for name, actions in screens.items():
                wanted.setdefault(name, set()).update(actions)

        rows = UserScreen.objects.filter(
            userscreen_name__in=wanted, is_deleted=False
        ).select_related("mainscreen_id")

        return [(row, sorted(wanted[row.userscreen_name])) for row in rows]

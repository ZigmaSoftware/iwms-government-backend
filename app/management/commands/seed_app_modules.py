"""Populate the App Module master (Screen Management > App Modules).

The App Modules screen reads a plain table (`AppModule`) that nothing but a
seeder ever writes to — there is no migration data load and `create` is
refused on the admin API itself (see `AppModuleViewSet.create`: "App modules
are defined by the mobile app build and cannot be created here"). The one
place that populates it is `PermissionSeeder._seed_mobile_app_catalog`, run
as part of `python manage.py seed --group screen-managements` — but that
top-level `seed` command refuses to run at all once `ENVIRONMENT=production`
/ `DEBUG=False` (see `seed.py`), and even where it's allowed, that group also
runs `CorporationPermissionSeeder`, which grants specific screen permissions
to named Erode corp admin/supervisor accounts — not something to run
unattended against a live system's real staff records just to fix an empty
catalog page.

This command does ONLY the App Module part: same
`PermissionSeeder._seed_mobile_app_catalog` call the full seed uses (single
source of truth, not reimplemented), nothing else. It is additive/idempotent
(get_or_create keyed on module_key) and safe to re-run — a second run
touches nothing new. No production guard, unlike `seed.py`: this is exactly
the kind of one-time catalog fix that's meant to run once directly against a
live database once the code merges (compare `backfill_app_access.py`, the
sibling one-off command this mirrors the --apply/dry-run shape of).

    python manage.py seed_app_modules            # show what it would do
    python manage.py seed_app_modules --apply
"""

from django.core.management.base import BaseCommand

from app.management.commands.seeders.superadmin.screen_management.permissions import (
    PermissionSeeder,
)
from app.models.superadmin.screen_management.app_module import AppModule


class Command(BaseCommand):
    help = "Seed the App Module master (Screen Management > App Modules) if it's empty/stale."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the changes. Without it, only reports what would happen.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        before = list(
            AppModule.objects.filter(is_deleted=False).values_list("module_key", flat=True)
        )

        if not apply_changes:
            from app.utils.app_feature_grants import APP_MODULE_SEED

            missing = [
                entry["module_key"]
                for entry in APP_MODULE_SEED
                if entry["module_key"] not in before
            ]
            self.stdout.write(self.style.WARNING(
                f"DRY RUN — {len(before)} module(s) already present: "
                f"{', '.join(before) or '(none)'}"
            ))
            self.stdout.write(self.style.WARNING(
                f"Would create {len(missing)} module(s): "
                f"{', '.join(missing) or '(none)'}. Re-run with --apply."
            ))
            return

        PermissionSeeder()._seed_mobile_app_catalog()

        after = list(
            AppModule.objects.filter(is_deleted=False).values_list("module_key", flat=True)
        )
        created = [key for key in after if key not in before]
        self.stdout.write(self.style.SUCCESS(
            f"Done. {len(after)} module(s) total; created {len(created)}: "
            f"{', '.join(created) or '(none — already up to date)'}"
        ))

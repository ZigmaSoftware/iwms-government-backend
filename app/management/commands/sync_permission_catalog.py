from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from app.utils.permission_catalog import SCREEN_STRUCTURE
from app.utils.permission_catalog_export import (
    FRONTEND_CATALOG_PATH,
    render_typescript,
)


class Command(BaseCommand):
    help = (
        "Write iwms-government-frontend/src/generated/permissionCatalog.ts from "
        "app/utils/permission_catalog.py. Use --check in CI to fail when it "
        "is stale."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            action="store_true",
            help="Exit with an error instead of writing when the file is stale.",
        )

    def handle(self, *args, check=False, **options):
        expected = render_typescript()
        path = FRONTEND_CATALOG_PATH
        current = path.read_text() if path.exists() else None

        # A backend-only checkout (e.g. a server) has no frontend to write to.
        if not path.parents[1].is_dir():
            self.stdout.write(f"No frontend checkout at {path.parents[2]}; skipped writing.")
            self._report_unseeded_screens()
            return

        if current == expected:
            self.stdout.write(f"{path} is up to date.")
        elif check:
            raise CommandError(
                f"{path} is stale. Run: python manage.py sync_permission_catalog"
            )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected)
            self.stdout.write(self.style.SUCCESS(f"Wrote {path}"))

        self._report_unseeded_screens()

    def _report_unseeded_screens(self):
        """Catalog screens with no active UserScreen row in this database.

        A screen missing here never appears in the permission forms, even
        though the sidebar and middleware already know it.
        """
        from app.models.superadmin.screen_management.mainscreen import MainScreen
        from app.models.superadmin.screen_management.userscreen import UserScreen

        try:
            mainscreens = dict(
                MainScreen.objects.filter(is_deleted=False)
                .values_list("unique_id", "mainscreen_name")
            )
            seeded = {
                (mainscreens.get(main_id), name)
                for main_id, name in UserScreen.objects.filter(
                    is_active=True, is_deleted=False
                ).values_list("mainscreen_id", "userscreen_name")
            }
        except DatabaseError as exc:
            self.stdout.write(f"Skipped database check ({exc.__class__.__name__}).")
            return

        missing = [
            f"{module}/{name}"
            for module, names in SCREEN_STRUCTURE.items()
            for name in names
            if (module, name) not in seeded
        ]
        if missing:
            self.stdout.write(self.style.WARNING(
                "Not seeded in this database, so not shown in the permission "
                f"forms: {', '.join(missing)}. Run the permission seeder."
            ))
        else:
            self.stdout.write("Every catalog screen is seeded in this database.")

"""Backfill the dedicated import/export screen permissions.

Uploads (POST .../bulk-upload/) now require the "import" permission and the
Downloads menu requires "export" — independently of "add"/"view". To keep
everyone's current access, this grants (once, idempotently):

    add  -> import
    view -> export

on both grant tables (UserScreenPermission role/local-body grants and
StaffAccessConfigurationPermission per-staff grants).

    python manage.py backfill_import_export_permissions          # dry run
    python manage.py backfill_import_export_permissions --apply  # write
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.models.superadmin.screen_management.userscreenpermission import UserScreenPermission
from app.models.superadmin.staff_management.staff_access_configuration import (
    StaffAccessConfigurationPermission,
)

MAPPINGS = (("add", "import"), ("view", "export"))

# Fields identifying "the same grant" on each table (besides the action).
KEY_FIELDS = {
    UserScreenPermission: (
        "usertype_id",
        "staffusertype_id",
        "contractorusertype_id",
        "governmentusertype_id",
        "state_id",
        "district_id",
        "area_type_id",
        "local_body_type",
        "local_body_id",
        "permission_owner_kind",
        "staff_id",
        "mainscreen_id",
        "userscreen_id",
    ),
    StaffAccessConfigurationPermission: (
        "staff_access_configuration_id",
        "mainscreen_id",
        "userscreen_id",
    ),
}

COPYABLE_EXCLUDE = {"unique_id", "id", "created_at", "updated_at"}


class Command(BaseCommand):
    help = "Grant import where add is granted and export where view is granted."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the grants (default is a dry run).",
        )

    def _action_id(self, name):
        row = (
            UserScreenAction.objects.filter(is_deleted=False)
            .filter(Q(variable_name__iexact=name) | Q(action_name__iexact=name))
            .first()
        )
        return row.unique_id if row else None

    def handle(self, *args, **options):
        apply = options["apply"]

        for name in ("import", "export"):
            UserScreenAction.objects.update_or_create(
                action_name=name,
                defaults={"variable_name": name, "is_active": True, "is_deleted": False},
            )

        ids = {name: self._action_id(name) for pair in MAPPINGS for name in pair}
        if not all(ids.values()):
            self.stdout.write(self.style.ERROR(f"Could not resolve actions: {ids}"))
            return

        total = 0
        with transaction.atomic():
            for model, label in (
                (UserScreenPermission, "role/local-body"),
                (StaffAccessConfigurationPermission, "staff"),
            ):
                key_fields = KEY_FIELDS[model]
                copy_fields = [
                    f.name
                    for f in model._meta.concrete_fields
                    if f.name not in COPYABLE_EXCLUDE and f.editable
                ]
                for source, target in MAPPINGS:
                    twins = 0
                    for row in (
                        model.objects.filter(
                            is_deleted=False, userscreenaction_id=ids[source]
                        )
                        .order_by("pk")
                        .iterator()
                    ):
                        twin_filter = {
                            field: getattr(row, field) for field in key_fields
                        }
                        twin_filter["userscreenaction_id"] = ids[target]
                        if model.objects.filter(
                            is_deleted=False, **twin_filter
                        ).exists():
                            continue
                        if apply:
                            data = {
                                field: getattr(row, field) for field in copy_fields
                            }
                            data["userscreenaction_id"] = ids[target]
                            try:
                                model.objects.create(**data)
                            except Exception as exc:
                                self.stdout.write(
                                    self.style.WARNING(f"Skipped {row.pk}: {exc}")
                                )
                                continue
                        twins += 1
                    self.stdout.write(
                        f"{label} grants: {source} -> {target}: "
                        f"{twins} {'created' if apply else 'to create'}"
                    )
                    total += twins

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {total} grants "
                f"{'created' if apply else 'to create (dry run — rerun with --apply)'}."
            )
        )

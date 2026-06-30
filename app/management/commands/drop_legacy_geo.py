"""
GATED removal of the legacy static geographical masters.

This is the final "contract" step of the expand -> migrate -> contract plan.
Run it ONLY after you have verified that:
  1. `python manage.py seed --group masters` mirrored geo into the hierarchy, and
  2. every dependent record now has a `location_node` (run with --check first).

It is intentionally a management command (not an auto-applied migration) so it
is never executed by a plain `migrate`. By default it runs in DRY-RUN mode and
changes nothing; pass --apply to actually remove data.

What --apply does (in order):
  - Verifies all customers/staff/leaders have location_node set (unless --force).
  - Soft-deletes legacy geo rows (Panchayat, AreaType, District, State, Country,
    Continent) so any lingering FK reads return nothing, WITHOUT a destructive
    schema change.

NOTE: physically dropping the columns/tables is a follow-up schema migration you
generate after also removing the old FK fields from the model files. This command
handles the safe data-level retirement; the tutorial documents the schema step.
"""

from django.core.management.base import BaseCommand


GEO_MODELS = [
    ("app.models.masters.panchayat", "Panchayat"),
    ("app.models.masters.areatype", "AreaType"),
    ("app.models.masters.district", "District"),
    ("app.models.common_masters.state", "State"),
    ("app.models.common_masters.country", "Country"),
    ("app.models.common_masters.continent", "Continent"),
]


class Command(BaseCommand):
    help = "Gated retirement of legacy geographical masters (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Actually soft-delete legacy geo rows.")
        parser.add_argument("--force", action="store_true",
                            help="Skip the location_node coverage safety check.")
        parser.add_argument("--check", action="store_true",
                            help="Only report dependent coverage and exit.")

    def handle(self, *args, **opts):
        from importlib import import_module

        coverage = self._coverage()
        self.stdout.write("Dependent location_node coverage:")
        for label, total, with_node in coverage:
            self.stdout.write(f"  {label}: {with_node}/{total} have location_node")

        if opts["check"]:
            return

        missing = [c for c in coverage if c[1] and c[2] < c[1]]
        if missing and not opts["force"]:
            self.stdout.write(self.style.ERROR(
                "Some dependents still lack location_node. Run "
                "`seed --group masters` to backfill, or pass --force to override."
            ))
            if not opts["apply"]:
                pass
            else:
                return

        if not opts["apply"]:
            self.stdout.write(self.style.WARNING(
                "DRY RUN — no data changed. Re-run with --apply to retire legacy geo."
            ))
            return

        for module_path, cls_name in GEO_MODELS:
            model = getattr(import_module(module_path), cls_name)
            qs = model.objects.filter(is_deleted=False)
            count = qs.count()
            # Soft delete (BaseMaster) — non-destructive, reversible.
            for obj in qs:
                obj.delete()
            self.stdout.write(self.style.SUCCESS(f"Retired {count} {cls_name} rows (soft-deleted)."))

        self.stdout.write(self.style.SUCCESS(
            "Legacy geo data retired. Geography now lives entirely in the Hierarchy Tree."
        ))

    def _coverage(self):
        out = []
        try:
            from app.models.customers.customercreation import CustomerCreation
            out.append((
                "customer",
                CustomerCreation.objects.filter(is_deleted=False).count(),
                CustomerCreation.objects.filter(is_deleted=False, location_node__isnull=False).count(),
            ))
        except Exception:
            pass
        try:
            from app.models.user_creations.staffcreation import StaffcreationOfficeDetails
            out.append((
                "staff",
                StaffcreationOfficeDetails.objects.filter(is_deleted=False).count(),
                StaffcreationOfficeDetails.objects.filter(is_deleted=False, location_node__isnull=False).count(),
            ))
        except Exception:
            pass
        try:
            from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin
            out.append((
                "panchayat_leader",
                PanchayatLeaderLogin.objects.filter(is_deleted=False).count(),
                PanchayatLeaderLogin.objects.filter(is_deleted=False, location_node__isnull=False).count(),
            ))
        except Exception:
            pass
        return out

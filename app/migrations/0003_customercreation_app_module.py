# Hand-written — not a plain `makemigrations` output.
#
# WHY THIS EXISTS: `app/migrations/*` is entirely gitignored except a couple
# of hand-picked exceptions (see `.gitignore`) — `0001_initial.py` is a huge,
# machine-generated snapshot that every environment quietly regenerates for
# itself against whatever `models.py` looks like *at the time*, and is never
# committed or shared. That means two environments can each show
# "0001_initial applied" in `django_migrations` while their real table
# schemas have drifted apart — Django only compares migration *names*, never
# their content, so this is invisible until a query hits the missing column.
#
# That is exactly what happened here: `CustomerCreation.app_module` (added
# for the App Module / Screen Management feature) is baked into every
# freshly-regenerated `0001_initial.py`, but the live server's own frozen
# copy predates the field, so `app_customercreation` on production has no
# `app_module` column at all — and since customer login runs a bare
# `CustomerCreation.objects.filter(...)` (selects every column), this broke
# EVERY customer login there with
# `OperationalError: Unknown column 'app_customercreation.app_module'`.
#
# A plain `AddField` migration (the usual `makemigrations` output, and how
# the one precedent for this pattern —
# `0002_dailytripcollectionpoint_carried_to_assignment_and_more.py`, since
# removed after everyone's local `0001_initial.py` had absorbed it — was
# written) is NOT safe to ship blindly this time: an environment (this one
# included) whose own `0001_initial.py` was regenerated *after* the field
# was added to the model already has the column, and a bare `AddField`
# would fail there with "Duplicate column". So the database operation below
# checks `information_schema` first and only adds the column if it is
# actually missing — safe to run unmodified on production (where it's
# missing) and on every dev machine (where it usually already exists).
#
# `SeparateDatabaseAndState` keeps Django's migration *state* in sync (so
# later migrations that touch this model still see the field) without
# forcing the *database* operation to run unconditionally.

from django.db import migrations, models

from app.utils.app_feature_grants import APP_MODULE_CHOICES

TABLE = "app_customercreation"
COLUMN = "app_module"


def add_app_module_column_if_missing(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
            [TABLE, COLUMN],
        )
        already_present = cursor.fetchone()[0] > 0

    if not already_present:
        schema_editor.execute(
            f"ALTER TABLE `{TABLE}` "
            f"ADD COLUMN `{COLUMN}` varchar(20) NOT NULL DEFAULT 'citizen'"
        )


def noop_reverse(apps, schema_editor):
    # Deliberately not dropping the column on reverse — a customer's
    # app_module value is real data, not migration scaffolding, and other
    # environments never had this migration add the column in the first
    # place (it was already there), so there's no single "undo" that's
    # correct everywhere.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0002_add_vehiclebreakdown_new_assignment"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="customercreation",
                    name="app_module",
                    field=models.CharField(
                        max_length=20,
                        choices=APP_MODULE_CHOICES,
                        default="citizen",
                        blank=True,
                        db_column="app_module",
                        help_text="Mobile app this customer lands in.",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    add_app_module_column_if_missing,
                    noop_reverse,
                ),
            ],
        ),
    ]

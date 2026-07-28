from django.db import models, transaction
from django.db.models import ForeignKey

from app.models.superadmin.screen_management.userscreencolumn import UserScreenColumn
from app.utils.model_mapper import iter_model_columns, resolve_userscreen_model


SEARCHABLE_FIELD_TYPES = {
    "CharField",
    "TextField",
    "EmailField",
    "URLField",
    "SlugField",
}


def _field_default(field):
    default = getattr(field, "default", models.NOT_PROVIDED)
    if default is None or default == models.NOT_PROVIDED:
        return None
    if callable(default):
        return getattr(default, "__name__", str(default))
    return str(default)


def _field_metadata(field, order_no):
    data = {
        "display_name": str(getattr(field, "verbose_name", field.name) or field.name).title(),
        "data_type": field.get_internal_type(),
        "db_column": field.db_column or field.column or field.name,
        "max_length": getattr(field, "max_length", None),
        "default_value": _field_default(field),
        "is_required": not getattr(field, "null", False) and not getattr(field, "blank", False),
        "is_nullable": getattr(field, "null", False),
        "is_unique": getattr(field, "unique", False),
        "is_primary_key": getattr(field, "primary_key", False),
        "is_foreign_key": isinstance(field, ForeignKey),
        "is_visible": True,
        "is_editable": getattr(field, "editable", True),
        "is_filterable": True,
        "is_searchable": field.get_internal_type() in SEARCHABLE_FIELD_TYPES,
        "is_sortable": True,
        "order_no": order_no,
    }

    if isinstance(field, ForeignKey):
        related_model = field.related_model
        data["related_model"] = related_model.__name__
        data["related_app"] = related_model._meta.app_label
    else:
        data["related_model"] = None
        data["related_app"] = None

    return data


@transaction.atomic
def sync_userscreen_schema(userscreen):
    model_class = resolve_userscreen_model(userscreen)
    if not model_class:
        return {
            "userscreen_id": userscreen.unique_id,
            "model": None,
            "created": [],
            "updated": [],
            "disabled": [],
        }

    if (
        userscreen.model_app_label != model_class._meta.app_label
        or userscreen.model_name != model_class.__name__
    ):
        userscreen.model_app_label = model_class._meta.app_label
        userscreen.model_name = model_class.__name__
        userscreen.save(update_fields=["model_app_label", "model_name", "updated_at"])

    existing_columns = {
        obj.field_name: obj
        for obj in UserScreenColumn.objects.select_for_update().filter(
            userscreen_id=userscreen,
            is_deleted=False,
        )
    }

    created = []
    updated = []
    active_field_names = set()

    for order_no, field in enumerate(iter_model_columns(model_class), start=1):
        active_field_names.add(field.name)
        metadata = _field_metadata(field, order_no)
        column = existing_columns.get(field.name)

        if column:
            changed = False
            for key, value in metadata.items():
                if getattr(column, key) != value:
                    setattr(column, key, value)
                    changed = True
            if not column.is_active:
                column.is_active = True
                changed = True
            if changed:
                column.save(update_fields=[*metadata.keys(), "is_active", "updated_at"])
                updated.append(column)
            continue

        created.append(
            UserScreenColumn.objects.create(
                userscreen_id=userscreen,
                field_name=field.name,
                **metadata,
            )
        )

    disabled = []
    for field_name, column in existing_columns.items():
        if field_name not in active_field_names and column.is_active:
            column.is_active = False
            column.save(update_fields=["is_active", "updated_at"])
            disabled.append(column)

    return {
        "userscreen_id": userscreen.unique_id,
        "model": f"{model_class._meta.app_label}.{model_class.__name__}",
        "created": created,
        "updated": updated,
        "disabled": disabled,
    }


def sync_screen_columns(userscreen):
    result = sync_userscreen_schema(userscreen)
    return [*result["created"], *result["updated"]]


@transaction.atomic
def sync_all_screens():
    from app.models.superadmin.screen_management.userscreen import UserScreen

    results = {
        "total_screens": 0,
        "successful_syncs": 0,
        "failed_syncs": 0,
        "errors": [],
    }

    screens = UserScreen.objects.filter(is_deleted=False)
    results["total_screens"] = screens.count()

    for screen in screens:
        try:
            sync_userscreen_schema(screen)
            results["successful_syncs"] += 1
        except Exception as exc:
            results["failed_syncs"] += 1
            results["errors"].append(f"{screen.unique_id}: {exc}")

    return results


def detect_schema_changes(userscreen):
    model_class = resolve_userscreen_model(userscreen)
    changes = {
        "has_changes": False,
        "added_fields": [],
        "removed_fields": [],
        "modified_fields": [],
    }
    if not model_class:
        return changes

    django_fields = {field.name: field for field in iter_model_columns(model_class)}
    screen_columns = {
        column.field_name: column
        for column in UserScreenColumn.objects.filter(userscreen_id=userscreen, is_deleted=False)
    }

    changes["added_fields"] = sorted(set(django_fields) - set(screen_columns))
    changes["removed_fields"] = sorted(set(screen_columns) - set(django_fields))

    for field_name in set(django_fields).intersection(screen_columns):
        field = django_fields[field_name]
        column = screen_columns[field_name]
        metadata = _field_metadata(field, column.order_no)
        if any(getattr(column, key) != value for key, value in metadata.items()):
            changes["modified_fields"].append(field_name)

    changes["has_changes"] = bool(
        changes["added_fields"] or changes["removed_fields"] or changes["modified_fields"]
    )
    return changes

# core/management/commands/seeders/base.py
from django.db import transaction


class BaseSeeder:
    name = "base"

    @transaction.atomic
    def run(self):
        raise NotImplementedError("---Seeder must implement run()---")

    @staticmethod
    def pick_existing(model, **lookup):
        """Return one row matching `lookup`, or None.

        Master names aren't unique in the schema, so a DB that has been used
        through the UI can hold duplicates (soft-deleted + re-created rows).
        `.get()` / `update_or_create()` raise MultipleObjectsReturned there;
        this deterministically prefers a live row (not deleted, active), then
        the lowest pk, so every seeder resolves the same record."""
        qs = model.objects.filter(**lookup)
        field_names = {f.name for f in model._meta.get_fields()}
        ordering = []
        if "is_deleted" in field_names:
            ordering.append("is_deleted")
        if "is_active" in field_names:
            ordering.append("-is_active")
        ordering.append("pk")
        return qs.order_by(*ordering).first()

    def upsert(self, model, defaults=None, **lookup):
        """Duplicate-tolerant update_or_create(); returns (obj, created)."""
        defaults = defaults or {}
        obj = self.pick_existing(model, **lookup)
        if obj is None:
            return model.objects.create(**lookup, **defaults), True
        for key, value in defaults.items():
            setattr(obj, key, value)
        obj.save()
        return obj, False

    def log(self, message):
        print(f"[{self.name.upper()}] {message}")

    def log_error(self, message):
        print(f"[{self.name.upper()} ERROR] {message}")
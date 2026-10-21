# core/management/commands/seeders/base.py
from django.db import transaction
from django.utils import timezone

from app.cache.invalidation import invalidate_scope


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

    def bulk_upsert(self, model, rows, key_fields, scope=None, batch_size=500):
        """upsert() for thousands of rows in a few queries; returns
        (created, updated).

        `rows` are dicts of field values; each is matched to an existing row
        on `key_fields` (within `scope`, a filter dict narrowing which rows
        are loaded), preferring a live row exactly like pick_existing().
        Only rows whose values actually changed are written. bulk_* skips
        save()/signals — fine for the plain geo masters this is used for."""
        field_names = {f.name for f in model._meta.get_fields()}
        ordering = [f for f in ("is_deleted", "-is_active") if f.lstrip("-") in field_names] + ["pk"]

        existing = {}
        for obj in model.objects.filter(**(scope or {})).order_by(*ordering):
            existing.setdefault(tuple(getattr(obj, f) for f in key_fields), obj)

        update_fields = sorted({f for row in rows for f in row} - set(key_fields))
        if "updated_at" in field_names:
            update_fields.append("updated_at")
        now = timezone.now()

        to_create, to_update, seen_pks = [], [], set()
        for row in rows:
            obj = existing.get(tuple(row[f] for f in key_fields))
            if obj is None:
                obj = model(**row)
                while obj.pk in seen_pks:  # time-based ids can repeat in a tight loop
                    obj.pk = model._meta.pk.get_default()
                seen_pks.add(obj.pk)
                to_create.append(obj)
            elif any(getattr(obj, f) != v for f, v in row.items()):
                for f, v in row.items():
                    setattr(obj, f, v)
                if "updated_at" in field_names:
                    obj.updated_at = now
                to_update.append(obj)

        model.objects.bulk_create(to_create, batch_size=batch_size)
        if to_update:
            model.objects.bulk_update(to_update, update_fields, batch_size=batch_size)
        invalidate_scope(*getattr(model, "CACHE_SCOPES", ()))
        return len(to_create), len(to_update)

    def log(self, message):
        print(f"[{self.name.upper()}] {message}")

    def log_error(self, message):
        print(f"[{self.name.upper()} ERROR] {message}")
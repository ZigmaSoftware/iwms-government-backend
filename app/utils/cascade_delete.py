"""
Generic, declarative cascade-soft-delete for BaseMaster subclasses.

Each model that should sweep child rows when it is soft-deleted declares a
CASCADE_SOFT_DELETE class attribute - a tuple of reverse-relation accessor
names (the related_name used on the child FK/M2M, exactly as you'd write
`instance.<related_name>`). The child model's own CASCADE_SOFT_DELETE (if
any) is walked transitively by the same function, so a model only needs to
list its OWN direct children, not its whole descendant tree.

Usage:

    class Continent(BaseMaster):
        CASCADE_SOFT_DELETE = ("countries", "states", "districts")
        ...

Models that are NOT soft-deletable (no is_deleted field, e.g. TripAttendance,
AlternativeStaffTemplate, StaffAudit) must never appear in a
CASCADE_SOFT_DELETE tuple - there is nothing for the cascade to flip, and
those tables are intentionally left untouched (audit/log-shaped tables in
particular are meant to be permanent).

ManyToMany relations (e.g. StaffDataScope.wards, TripPlan.wards) are also
deliberately excluded from this mechanism: soft-deleting the target of an
M2M link doesn't make sense - unlinking is a different, smaller operation
and is out of scope here.
"""
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction


def cascade_soft_delete(instance, updated_by=None):
    """
    Soft-delete `instance` and, transitively, every row reachable via the
    reverse relations named in `type(instance).CASCADE_SOFT_DELETE` (and in
    turn those descendants' own CASCADE_SOFT_DELETE), each exactly once.

    - Deduplicates by (model, pk) so a row reachable by more than one path
      (e.g. a State reachable both via Continent.states directly and via
      Continent -> Country -> State) is only ever updated once.
    - Performs one bulk `.filter(pk__in=[...]).update(is_deleted=True,
      is_active=False, ...)` per model collected, instead of per-instance
      .save()/.delete() calls, for efficiency at scale.
    - When `updated_by` (an Account instance) is given, it is stamped onto
      every row's `updated_by` field in the same bulk update, on every
      model that declares that field - so cascaded rows record who
      triggered the delete, not just the top-level instance.
    - Wrapped in a single transaction.atomic() so a partial cascade can
      never be left half-applied.

    Bulk `.update()` does not invoke each row's `delete()`/`save()` override
    or fire Django signals. This is safe today because every affected
    model's delete() (where overridden) is a trivial is_deleted/is_active
    flip with no other side effects (verified across the codebase). Any
    model added to a CASCADE_SOFT_DELETE tuple in future must keep its
    delete-time side effects (if it ever needs any) out of delete() itself
    (e.g. in a pre_save signal keyed off an is_deleted transition) rather
    than relying on delete() being called per-instance, since this cascade
    bypasses it.
    """
    visited: dict[type, set] = {}

    def _walk(obj):
        model = type(obj)
        pks = visited.setdefault(model, set())
        if obj.pk in pks:
            return
        pks.add(obj.pk)

        for rel_name in getattr(model, "CASCADE_SOFT_DELETE", ()):
            try:
                related = getattr(obj, rel_name, None)
            except ObjectDoesNotExist:
                # Reverse OneToOne accessor raises when no related row exists.
                continue
            if related is None:
                continue
            if hasattr(related, "all"):
                # Reverse FK / M2M manager — iterate every related row.
                for child in related.all().iterator():
                    _walk(child)
            else:
                # Reverse OneToOne accessor — a single model instance.
                _walk(related)

    _walk(instance)

    with transaction.atomic():
        for model, pks in visited.items():
            update_fields = {"is_deleted": True, "is_active": False}
            if updated_by is not None:
                try:
                    model._meta.get_field("updated_by")
                    update_fields["updated_by"] = updated_by
                except Exception:
                    pass
            model.objects.filter(pk__in=pks, is_deleted=False).update(**update_fields)


def collect_cascade_cache_scopes(instance):
    """
    Returns the de-duplicated union of CACHE_SCOPES declared on `instance`'s
    model and every model reachable through its CASCADE_SOFT_DELETE chain
    (regardless of whether any rows of that model actually existed to
    delete - cheap to over-invalidate a cache scope, expensive to under
    invalidate one). Call this BEFORE cascade_soft_delete() mutates rows if
    you need scopes for models that end up with zero matching rows too;
    walking model classes (not instances) means it works even with no data.
    """
    scopes: set[str] = set()
    seen_models: set[type] = set()

    def _walk_model(model):
        if model in seen_models:
            return
        seen_models.add(model)
        scopes.update(getattr(model, "CACHE_SCOPES", ()))
        for rel_name in getattr(model, "CASCADE_SOFT_DELETE", ()):
            field = _resolve_child_model(model, rel_name)
            if field is not None:
                _walk_model(field)

    def _resolve_child_model(model, rel_name):
        try:
            rel = model._meta.get_field(rel_name)
        except Exception:
            return None
        related_model = getattr(rel, "related_model", None)
        return related_model

    _walk_model(type(instance))
    return tuple(scopes)

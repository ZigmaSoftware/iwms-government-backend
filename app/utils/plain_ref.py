"""Helpers for plain unique_id reference columns (no ForeignKeys)."""


def ref_id(value):
    """Return the reference id for a model instance, or the value itself if
    it is already a plain id (or None). Plain reference columns hold the
    target's `unique_id` (staff: `staff_unique_id`), which is not always its
    pk (DailyTripAssignment's pk is an integer `id`), so prefer those."""
    if value is None or isinstance(value, (str, int)):
        return value
    for attr in ("unique_id", "staff_unique_id"):
        ref = getattr(value, attr, None)
        if ref is not None:
            return ref
    return getattr(value, "pk", value)


def json_contains_any(field, values):
    """Q matching rows whose JSON list `field` contains any of `values`
    (replacement for an M2M `field__unique_id__in=values` lookup)."""
    from functools import reduce
    import operator

    from django.db.models import Q

    values = [v for v in values if v]
    if not values:
        return Q(pk__in=[])
    return reduce(operator.or_, (Q(**{f"{field}__contains": v}) for v in values))


def ref_q(path, model, key="unique_id", **filters):
    """Q for `path` (a plain unique_id column, possibly reached through
    other lookups) pointing at a `model` row matching `filters` — the
    no-join replacement for `path__<field>=value`."""
    from django.db.models import Q

    return Q(**{f"{path}__in": model.objects.filter(**filters).values(key)})


def ref_value(path, model, field, key="unique_id"):
    """Subquery expression for `model.<field>` of the row whose `key`
    equals the plain id at `path` — the no-join replacement for
    annotating / grouping by `path__<field>`."""
    from django.db.models import OuterRef, Subquery

    return Subquery(model.objects.filter(**{key: OuterRef(path)}).values(field)[:1])

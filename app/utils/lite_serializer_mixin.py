from rest_framework import serializers


def make_lite_serializer(model, name_field, source=None, extra_fields=()):
    """Build a minimal ModelSerializer exposing only unique_id + name_field
    (plus any extra_fields), for ?lite=1 dropdown/lookup responses.

    `source` lets name_field be an alias for a differently-named model field
    (e.g. name_field="state_name", source="name"), mirroring how the full
    serializer exposes it, so frontend code reading response.state_name
    keeps working unchanged.
    """
    fields = ["unique_id", name_field, *extra_fields]
    meta_attrs = {"model": model, "fields": fields}
    # Marks the output columns as fully known (see LiteListMixin).
    serializer_attrs = {"Meta": type("Meta", (), meta_attrs), "lite_columns_known": True}

    if source and source != name_field:
        serializer_attrs[name_field] = serializers.CharField(source=source, read_only=True)

    return type(f"Lite{model.__name__}Serializer", (serializers.ModelSerializer,), serializer_attrs)


class LiteListMixin:
    """Opt-in ?lite=1 support: swaps in a minimal id+name serializer for this
    request only. Default behavior (no ?lite param) is unchanged."""

    lite_serializer_class = None

    def _is_lite(self):
        return bool(self.request.query_params.get("lite")) and self.lite_serializer_class is not None

    def get_serializer_class(self):
        if self._is_lite():
            return self.lite_serializer_class
        return super().get_serializer_class()

    def filter_queryset(self, queryset):
        # Hooked here, not get_queryset(): most lite viewsets override
        # get_queryset() without calling super().
        queryset = super().filter_queryset(queryset)
        if (
            self._is_lite()
            and getattr(self, "action", None) == "list"
            # Hand-written lite serializers may read other columns in methods.
            and getattr(self.lite_serializer_class, "lite_columns_known", False)
        ):
            # Load only the columns the lite serializer outputs — dropdown
            # lists span whole masters (12k+ panchayats), and the unused
            # columns (e.g. boundary `coordinates` JSON) dominate the cost.
            queryset = queryset.only(*lite_columns(self.lite_serializer_class))
        return queryset


def lite_columns(lite_serializer_class):
    """Concrete model columns behind a make_lite_serializer() class."""
    meta = lite_serializer_class.Meta
    concrete = {f.name for f in meta.model._meta.concrete_fields}
    declared = lite_serializer_class._declared_fields
    columns = set()
    for name in meta.fields:
        source = getattr(declared.get(name), "source", None) or name
        if source in concrete:
            columns.add(source)
    columns.add(meta.model._meta.pk.name)
    return sorted(columns)

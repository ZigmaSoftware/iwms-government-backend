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
    serializer_attrs = {"Meta": type("Meta", (), meta_attrs)}

    if source and source != name_field:
        serializer_attrs[name_field] = serializers.CharField(source=source, read_only=True)

    return type(f"Lite{model.__name__}Serializer", (serializers.ModelSerializer,), serializer_attrs)


class LiteListMixin:
    """Opt-in ?lite=1 support: swaps in a minimal id+name serializer for this
    request only. Default behavior (no ?lite param) is unchanged."""

    lite_serializer_class = None

    def get_serializer_class(self):
        if self.request.query_params.get("lite") and self.lite_serializer_class is not None:
            return self.lite_serializer_class
        return super().get_serializer_class()

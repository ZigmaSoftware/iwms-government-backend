"""Relation keys with or without the `_id` suffix.

Migration 0026 turned ForeignKeys like `category` into plain `category_id`
CharFields, which renamed their API keys too — clients (the admin complaint
forms, older mobile builds) still send and read `category`, `priority`,
`district`, ... This mixin accepts the bare key on input when the `_id` key
is absent, and adds the bare key to the output, so both spellings work.
"""


class BareIdKeysMixin:
    def _bare_id_pairs(self):
        model = self.Meta.model
        pk = model._meta.pk.attname
        pairs = []
        for field in model._meta.concrete_fields:
            attname = field.attname
            if attname == pk or not attname.endswith("_id"):
                continue
            bare = attname[: -len("_id")]
            # Never shadow a field the serializer declares under the bare name.
            if bare in self.fields:
                continue
            pairs.append((bare, attname))
        return pairs

    def to_internal_value(self, data):
        if hasattr(data, "copy") and hasattr(data, "keys"):
            aliased = [(bare, attname) for bare, attname in self._bare_id_pairs() if bare in data and attname not in data]
            if aliased:
                data = data.copy()
                for bare, attname in aliased:
                    data[attname] = data.get(bare)
        return super().to_internal_value(data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for bare, attname in self._bare_id_pairs():
            if attname in data and bare not in data:
                data[bare] = data[attname]
        return data

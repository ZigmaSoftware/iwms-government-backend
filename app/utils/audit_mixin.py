from django.forms.models import model_to_dict
from django.db.models.fields.files import FieldFile
from app.utils.common_audit import CommonAudit
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID
from django.db.models.fields.files import FieldFile


class AuditViewSetMixin:

    AUDIT_MODULE = None
    AUDIT_ENDPOINT = None
    AUDIT_REDACT_FIELDS = set()

    @classmethod
    def get_extra_actions(cls):
        """
        Provide compatibility with DRF routers which call
        ``viewset.get_extra_actions()`` on the viewset class. If a
        superclass provides this method, delegate to it; otherwise
        return an empty list.
        """
        for base in cls.__mro__[1:]:
            if hasattr(base, "get_extra_actions"):
                try:
                    return base.get_extra_actions()
                except Exception:
                    # If superclass method exists but fails, ignore and
                    # continue to next base.
                    continue

        return []

    def get_audit_object_id(self, instance):

        possible_fields = [
            "unique_id",
            "staff_unique_id",
            "id",
            "pk",
        ]

        for field in possible_fields:
            value = getattr(instance, field, None)
            if value:
                return str(value)

        return None

    def _serialize_instance(self, instance):
        data = model_to_dict(instance)

        for field in instance._meta.fields:
            value = getattr(instance, field.name)

            # ForeignKey → store unique_id
            if field.is_relation:
                data[field.name] = getattr(value, "unique_id", None) if value else None

            # Decimal → convert to float
            elif isinstance(value, Decimal):
                data[field.name] = float(value)

            # Datetime → convert to ISO string
            elif isinstance(value, (datetime, date, time)):
                data[field.name] = value.isoformat()

            elif isinstance(value, UUID):
                data[field.name] = str(value)

            elif isinstance(value, FieldFile):
                data[field.name] = value.name or None

            else:
                data[field.name] = value

        for field_name in self.AUDIT_REDACT_FIELDS:
            if field_name in data and data[field_name]:
                data[field_name] = "[REDACTED]"

        # M2M fields — convert to list of unique_ids (or PKs as fallback)
        for field in instance._meta.many_to_many:
            related_qs = getattr(instance, field.name).all()
            data[field.name] = [
                getattr(obj, "unique_id", None) or str(obj.pk)
                for obj in related_qs
            ]

        return data

    def log_audit(self, request, instance=None, previous_data=None, new_data=None):

        CommonAudit.objects.create(
            module_name=self.AUDIT_MODULE,
            endpoint_name=self.AUDIT_ENDPOINT,
            method=request.method,
            # object_id=getattr(instance, "unique_id", None),
            object_id=self.get_audit_object_id(instance),
            previous_data=previous_data,
            new_data=new_data,
            createdBy=str(request.user) if request.user.is_authenticated else "SYSTEM",
        )

    # CREATE
    def perform_create(self, serializer):
        super().perform_create(serializer)

        instance = serializer.instance
        new_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
            new_data=new_data
        )

    # UPDATE
    def perform_update(self, serializer):

        instance = serializer.instance
        previous_data = self._serialize_instance(instance)

        super().perform_update(serializer)

        updated_instance = serializer.instance
        new_data = self._serialize_instance(updated_instance)

        self.log_audit(
            self.request,
            instance=updated_instance,
            previous_data=previous_data,
            new_data=new_data
        )

    # DELETE
    def perform_destroy(self, instance):

        previous_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=None
        )

        super().perform_destroy(instance)

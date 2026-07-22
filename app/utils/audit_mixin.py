from django.forms.models import model_to_dict
from django.db.models.fields.files import FieldFile
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails
from app.utils.base_models import Account
from app.utils.common_audit import CommonAudit
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID
from django.db.models.fields.files import FieldFile


class AuditViewSetMixin:

    AUDIT_MODULE = None
    AUDIT_ENDPOINT = None
    AUDIT_REDACT_FIELDS = set()

    def _account_for_request_user(self):
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None

        if isinstance(user, StaffcreationOfficeDetails) or hasattr(user, "staff_unique_id"):
            account, _ = Account.objects.get_or_create(staff=user)
            return account

        if hasattr(user, "unique_id") or getattr(user, "pk", None):
            account, _ = Account.objects.get_or_create(user=user)
            return account

        return None

    @staticmethod
    def _model_has_field(model, field_name):
        try:
            model._meta.get_field(field_name)
            return True
        except Exception:
            return False

    def _audit_save_kwargs(self, *, create=False):
        model = getattr(getattr(self, "serializer_class", None), "Meta", None)
        model = getattr(model, "model", None)
        if model is None and hasattr(self, "get_serializer_class"):
            serializer_class = self.get_serializer_class()
            model = getattr(getattr(serializer_class, "Meta", None), "model", None)
        if model is None:
            return {}

        account = self._account_for_request_user()
        if not account:
            return {}

        kwargs = {}
        if create and self._model_has_field(model, "created_by"):
            kwargs["created_by"] = account
        if self._model_has_field(model, "updated_by"):
            kwargs["updated_by"] = account
        return kwargs

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
        serializer.save(**self._audit_save_kwargs(create=True))

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

        serializer.save(**self._audit_save_kwargs(create=False))

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

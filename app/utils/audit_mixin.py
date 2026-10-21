import logging

from django.forms.models import model_to_dict
from django.db.models.fields.files import FieldFile
from rest_framework.exceptions import ValidationError
from app.models.superadmin.staff_management.staffcreation import StaffcreationOfficeDetails
from app.utils.base_models import Account
from app.utils.audit_context import resolve_actor, stamp_audit_geo
from app.utils.common_audit import CommonAudit
from app.utils.delete_reason import (
    DELETE_REASON_FIELD,
    DELETE_REASON_MAX_LENGTH,
    read_delete_reason,
    reset_current_delete_reason,
    set_current_delete_reason,
)
from app.utils.hierarchy import FLAT_GEO_FIELDS
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID
from django.db.models.fields.files import FieldFile

logger = logging.getLogger(__name__)


def serialize_instance_for_audit(instance, redact_fields=()):
    """Standalone version of AuditViewSetMixin._serialize_instance for plain
    function-based views (e.g. mobile actions) that don't inherit the mixin."""
    data = model_to_dict(instance)

    for field in instance._meta.fields:
        value = getattr(instance, field.name)

        if field.is_relation:
            data[field.name] = getattr(value, "unique_id", None) if value else None
        elif isinstance(value, Decimal):
            data[field.name] = float(value)
        elif isinstance(value, (datetime, date, time)):
            data[field.name] = value.isoformat()
        elif isinstance(value, UUID):
            data[field.name] = str(value)
        elif isinstance(value, FieldFile):
            data[field.name] = value.name or None
        else:
            data[field.name] = value

    for field_name in redact_fields:
        if field_name in data and data[field_name]:
            data[field_name] = "[REDACTED]"

    for field in instance._meta.many_to_many:
        related_qs = getattr(instance, field.name).all()
        data[field.name] = [
            getattr(obj, "unique_id", None) or str(obj.pk)
            for obj in related_qs
        ]

    return data


def get_audit_object_id(instance):
    for field in ("unique_id", "staff_unique_id", "id", "pk"):
        value = getattr(instance, field, None)
        if value:
            return str(value)
    return None


def get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _write_audit(
    *, module_name, endpoint_name, method, instance, previous_data, new_data, created_by,
    ip_address=None, user_agent=None, success=True, reason=None, actor=None,
    delete_reason=None, request=None,
):
    """Write the CommonAudit row for one audited event."""
    if request is not None and getattr(request, "method", None) == "DELETE":
        delete_reason = delete_reason or read_delete_reason(request) or None
        # Lets DeleteReasonMixin skip its fallback audit row.
        request._delete_audit_logged = True
    object_id = get_audit_object_id(instance) if instance is not None else None
    created_by_id, created_by_name, created_by_type = resolve_actor(actor)
    common_audit = CommonAudit(
        module_name=module_name,
        endpoint_name=endpoint_name,
        method=method,
        object_id=object_id,
        previous_data=previous_data,
        new_data=new_data,
        createdBy=created_by,
        created_by_id=created_by_id,
        created_by_name=created_by_name,
        created_by_type=created_by_type,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
        reason=reason,
        delete_reason=delete_reason and str(delete_reason)[:DELETE_REASON_MAX_LENGTH],
    )

    # The changed record is the primary geo source; a scoped (non-super)
    # actor's own geo is only the fallback for records that carry none (e.g.
    # a failed create), so the row still lands in that actor's scope.
    stamp_audit_geo(common_audit, instance)
    if (
        actor is not None
        and not getattr(actor, "is_superuser", False)
        and not any(getattr(common_audit, field) for field in FLAT_GEO_FIELDS)
    ):
        stamp_audit_geo(common_audit, actor)

    common_audit.save()
    return common_audit


def log_common_audit(
    request, *, module_name, endpoint_name, instance=None,
    previous_data=None, new_data=None, success=True, reason=None,
    delete_reason=None,
):
    """Standalone version of AuditViewSetMixin.log_audit for plain
    function-based views (e.g. mobile actions) that don't inherit the mixin."""
    return _write_audit(
        module_name=module_name,
        endpoint_name=endpoint_name,
        method=request.method,
        instance=instance,
        previous_data=previous_data,
        new_data=new_data,
        created_by=str(request.user) if request.user.is_authenticated else "SYSTEM",
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT"),
        success=success,
        reason=reason,
        actor=getattr(request, "user", None),
        delete_reason=delete_reason,
        request=request,
    )


# Alias matching IWMS' name for the same helper.
write_common_audit = log_common_audit


class DeleteReasonMixin:
    """Requires a `delete_reason` on every DELETE request and records it.

    - Rejects the DELETE with 400 before anything is touched when the
      reason is missing.
    - Publishes the reason for the request so cascade_soft_delete() stamps
      it on the deleted row and every cascaded child.
    - After a successful destroy, stamps the reason on the row itself (for
      destroy paths that flip is_deleted by hand instead of calling
      delete()) and writes a CommonAudit row if the destroy path didn't.
    """

    AUDIT_MODULE = None
    AUDIT_ENDPOINT = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method != "DELETE":
            return

        reason = read_delete_reason(request)
        if not reason:
            raise ValidationError({DELETE_REASON_FIELD: ["Please enter the reason for deleting this record."]})
        if len(reason) > DELETE_REASON_MAX_LENGTH:
            raise ValidationError({
                DELETE_REASON_FIELD: [f"Ensure this field has no more than {DELETE_REASON_MAX_LENGTH} characters."]
            })
        self._delete_reason = reason
        self._delete_reason_token = set_current_delete_reason(reason)

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        finally:
            token = getattr(self, "_delete_reason_token", None)
            if token is not None:
                reset_current_delete_reason(token)
                self._delete_reason_token = None

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        reason = getattr(self, "_delete_reason", None)
        if reason and 200 <= response.status_code < 300:
            try:
                self._record_delete_reason(request, reason)
            except Exception:
                logger.exception(
                    "Failed to record delete reason for %s", self.__class__.__name__
                )
        return response

    def _deleted_instance(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        lookup_value = self.kwargs.get(lookup_url_kwarg)
        if lookup_value is None:
            return None
        model = self.get_queryset().model
        return model._base_manager.filter(**{self.lookup_field: lookup_value}).first()

    def _record_delete_reason(self, request, reason):
        from django.utils import timezone

        instance = self._deleted_instance()
        if instance is not None:
            stamp = {}
            if hasattr(instance, DELETE_REASON_FIELD):
                stamp["delete_reason"] = reason
                instance.delete_reason = reason
            # Manual destroy paths flip is_deleted by hand instead of calling
            # delete(): BaseMaster.save() already stamped deleted_at on the
            # save, but the actor and updated_at are only known here.
            account_fn = getattr(self, "_account_for_request_user", None)
            account = account_fn() if callable(account_fn) else None
            has_field = getattr(self, "_model_has_field", None)

            def _has(model, name):
                if callable(has_field):
                    return has_field(model, name)
                try:
                    model._meta.get_field(name)
                    return True
                except Exception:
                    return False

            if _has(type(instance), "deleted_at") and not instance.deleted_at:
                stamp["deleted_at"] = timezone.now()
                instance.deleted_at = stamp["deleted_at"]
            if account is not None and _has(type(instance), "deleted_by"):
                stamp["deleted_by"] = account.pk
                instance.deleted_by = account.pk
            if _has(type(instance), "updated_at"):
                stamp["updated_at"] = timezone.now()
                instance.updated_at = stamp["updated_at"]
            if stamp:
                type(instance)._base_manager.filter(pk=instance.pk).update(**stamp)

        if not getattr(request, "_delete_audit_logged", False):
            _write_audit(
                module_name=self.AUDIT_MODULE or self.__class__.__name__,
                endpoint_name=self.AUDIT_ENDPOINT or self.__class__.__name__,
                method=request.method,
                instance=instance,
                previous_data=None,
                new_data=serialize_instance_for_audit(instance) if instance is not None else None,
                created_by=str(request.user) if request.user.is_authenticated else "SYSTEM",
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT"),
                actor=getattr(request, "user", None),
                delete_reason=reason,
                request=request,
            )


class AuditViewSetMixin(DeleteReasonMixin):

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
    def _model_field(model, field_name):
        try:
            return model._meta.get_field(field_name)
        except Exception:
            return None

    @classmethod
    def _model_has_field(cls, model, field_name):
        return cls._model_field(model, field_name) is not None

    @staticmethod
    def _account_field_value(field, account):
        if account is None:
            return None
        return account if getattr(field, "is_relation", False) else account.pk

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
        # Audit actor fields may be real relation fields on legacy models or
        # plain string account-id columns elsewhere. Stamp the shape each field uses.
        if create:
            field = self._model_field(model, "created_by")
            if field is not None:
                kwargs["created_by"] = self._account_field_value(field, account)
            elif self._model_has_field(model, "created_by_id"):
                kwargs["created_by_id"] = account.pk
        field = self._model_field(model, "updated_by")
        if field is not None:
            kwargs["updated_by"] = self._account_field_value(field, account)
        elif self._model_has_field(model, "updated_by_id"):
            kwargs["updated_by_id"] = account.pk
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

            # Relation field → store unique_id
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

    def log_audit(self, request, instance=None, previous_data=None, new_data=None, success=True, reason=None,
                    delete_reason=None):

        _write_audit(
            module_name=self.AUDIT_MODULE,
            endpoint_name=self.AUDIT_ENDPOINT,
            method=request.method,
            instance=instance,
            previous_data=previous_data,
            new_data=new_data,
            created_by=str(request.user) if request.user.is_authenticated else "SYSTEM",
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT"),
            success=success,
            reason=reason,
            actor=getattr(request, "user", None),
            delete_reason=delete_reason,
            request=request,
        )

    @staticmethod
    def _format_audit_error(exc):
        """Render a DRF/Django validation error into a short, readable
        string for the audit 'reason' column — e.g. a dropdown left empty
        surfaces as its serializer field error, not a raw exception repr."""
        detail = getattr(exc, "detail", None)
        if detail is None:
            return str(exc)[:255]

        parts = []

        def _walk(node, prefix=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    _walk(value, f"{prefix}{key}: " if not prefix else f"{prefix}{key}: ")
            elif isinstance(node, (list, tuple)):
                for item in node:
                    _walk(item, prefix)
            else:
                parts.append(f"{prefix}{node}")

        _walk(detail)
        message = "; ".join(parts) if parts else str(exc)
        return message[:255]

    # CREATE
    def perform_create(self, serializer):
        try:
            serializer.save(**self._audit_save_kwargs(create=True))
        except Exception as exc:
            self.log_audit(
                self.request,
                instance=None,
                previous_data=None,
                new_data=getattr(serializer, "initial_data", None),
                success=False,
                reason=self._format_audit_error(exc),
            )
            raise

        instance = serializer.instance
        new_data = self._serialize_instance(instance)

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=None,
            new_data=new_data,
            success=True,
        )

    # UPDATE
    def perform_update(self, serializer):

        instance = serializer.instance
        previous_data = self._serialize_instance(instance)

        try:
            serializer.save(**self._audit_save_kwargs(create=False))
        except Exception as exc:
            self.log_audit(
                self.request,
                instance=instance,
                previous_data=previous_data,
                new_data=getattr(serializer, "initial_data", None),
                success=False,
                reason=self._format_audit_error(exc),
            )
            raise

        updated_instance = serializer.instance
        new_data = self._serialize_instance(updated_instance)

        self.log_audit(
            self.request,
            instance=updated_instance,
            previous_data=previous_data,
            new_data=new_data,
            success=True,
        )

    # DELETE
    def perform_destroy(self, instance):

        previous_data = self._serialize_instance(instance)
        account = self._account_for_request_user()

        try:
            delete_kwargs = {"updated_by": account} if account is not None else {}
            instance.delete(**delete_kwargs)
        except Exception as exc:
            self.log_audit(
                self.request,
                instance=instance,
                previous_data=previous_data,
                new_data=None,
                success=False,
                reason=self._format_audit_error(exc),
            )
            raise

        self.log_audit(
            self.request,
            instance=instance,
            previous_data=previous_data,
            new_data=None,
            success=True,
        )

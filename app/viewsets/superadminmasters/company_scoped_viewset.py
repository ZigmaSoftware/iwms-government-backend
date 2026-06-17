from rest_framework import viewsets

from app.models.user_creations.staffcreation import Staffcreation
from app.utils.base_models import Account


class CompanyScopedViewSet(viewsets.ModelViewSet):

    # ==========================================================
    # HELPER — only pass created_by/updated_by if model supports it
    # ==========================================================

    def _build_save_kwargs(self, serializer, base_kwargs: dict, **audit_fields) -> dict:
        """
        Merges base_kwargs with audit fields (created_by, updated_by)
        only if the model actually has those fields.
        Prevents TypeError for models that don't extend BaseMaster.
        """
        model = getattr(getattr(serializer, "Meta", None), "model", None)
        result = dict(base_kwargs)

        for field_name, value in audit_fields.items():
            if model and hasattr(model, field_name):
                result[field_name] = value

        return result

    # ==========================================================
    # ACCOUNT RESOLUTION
    # ==========================================================

    def _get_account(self):
        user = self.request.user

        if not user or not user.is_authenticated:
            return None

        if isinstance(user, Staffcreation):
            account, _ = Account.objects.get_or_create(staff=user)
            return account

        account, _ = Account.objects.get_or_create(user=user)
        return account

    # ==========================================================
    # SUPERADMIN CHECK
    # ==========================================================

    def _is_platform_super_admin(self):
        user = getattr(self.request, "user", None)

        return bool(
            user
            and user.is_authenticated
            and getattr(user, "is_superuser", False)
        )

    # ==========================================================
    # CREATE
    # ==========================================================

    def perform_create(self, serializer):

        account = self._get_account()
        final_kwargs = self._build_save_kwargs(
            serializer, {}, created_by=account
        )
        serializer.save(**final_kwargs)

    # ==========================================================
    # UPDATE
    # ==========================================================

    def perform_update(self, serializer):

        account = self._get_account()
        final_kwargs = self._build_save_kwargs(
            serializer, {}, updated_by=account
        )
        serializer.save(**final_kwargs)

    # ==========================================================
    # DELETE (SOFT DELETE SUPPORT)
    # ==========================================================

    def perform_destroy(self, instance):

        account = self._get_account()

        if hasattr(instance, "is_deleted"):

            instance.is_deleted = True

            if hasattr(instance, "updated_by"):
                instance.updated_by = account

            instance.save()

        else:
            instance.delete()

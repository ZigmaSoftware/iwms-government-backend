import re

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models.customers.customercreation import CustomerCreation
from app.models.user_creations.staffcreation import Staffcreation
from app.utils.password_encryption import decrypt_password, encrypt_password


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "message": msg}, status=code)


def _ok(msg):
    return Response({"success": True, "message": msg}, status=status.HTTP_200_OK)


def _validate_password_complexity(password: str):
    """Return an error message if the password fails complexity rules, else None."""
    if len(password) < 6:
        return "Password must be at least 6 characters."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one numeric digit."
    return None


class ChangePasswordView(APIView):
    """
    POST /api/v1/auth/change-password/
    Authenticated endpoint. Works for staff and customer users.

    Body:
        old_password        (str) - current password
        new_password        (str) - desired new password
        confirm_new_password (str) - must match new_password
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get("old_password") or ""
        new_password = request.data.get("new_password") or ""
        confirm_new_password = request.data.get("confirm_new_password") or ""

        if not old_password or not new_password or not confirm_new_password:
            return _err("old_password, new_password, and confirm_new_password are required.")

        if new_password != confirm_new_password:
            return _err("New password and confirm password do not match.")

        complexity_error = _validate_password_complexity(new_password)
        if complexity_error:
            return _err(complexity_error)

        user = request.user
        user_type = getattr(user, "_user_type", None)

        # Resolve user type from JWT or model type
        if isinstance(user, Staffcreation):
            return self._change_staff_password(user, old_password, new_password)
        elif isinstance(user, CustomerCreation):
            return self._change_customer_password(user, old_password, new_password)

        # Fallback: try to locate by unique_id from token
        unique_id = getattr(user, "unique_id", None) or getattr(user, "staff_unique_id", None)
        if not unique_id:
            return _err("Unable to identify user.", status.HTTP_401_UNAUTHORIZED)

        staff = Staffcreation.objects.filter(staff_unique_id=unique_id, is_deleted=False).first()
        if staff:
            return self._change_staff_password(staff, old_password, new_password)

        customer = CustomerCreation.objects.filter(unique_id=unique_id, is_deleted=False).first()
        if customer:
            return self._change_customer_password(customer, old_password, new_password)

        return _err("User not found.", status.HTTP_404_NOT_FOUND)

    def _change_staff_password(self, staff, old_password, new_password):
        # Staff passwords are stored encrypted (Fernet), not hashed
        stored_decrypted = decrypt_password(staff.password or "")
        if stored_decrypted != old_password:
            return _err("Current password is incorrect.")

        if stored_decrypted == new_password:
            return _err("New password must be different from the current password.")

        staff.previous_password = staff.password
        staff.password = encrypt_password(new_password)
        staff.password_crt_date = timezone.now()
        staff.save(update_fields=["password", "previous_password", "password_crt_date"])
        return _ok("Password changed successfully.")

    def _change_customer_password(self, customer, old_password, new_password):
        # Customer passwords are Django-hashed
        if not customer.password or not check_password(old_password, customer.password):
            return _err("Current password is incorrect.")

        if check_password(new_password, customer.password):
            return _err("New password must be different from the current password.")

        customer.previous_password = customer.password
        customer.password = make_password(new_password)
        customer.password_crt_date = timezone.now()
        customer.save(update_fields=["password", "previous_password", "password_crt_date"])
        return _ok("Password changed successfully.")


class AdminChangePasswordView(APIView):
    """
    POST /api/v1/auth/admin-change-password/
    Admin-only endpoint to force-change a staff or customer password by unique_id.

    Body:
        target_type    (str) - "staff" or "customer"
        target_id      (str) - staff_unique_id or customer unique_id
        new_password   (str)
        confirm_new_password (str)
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        target_type = (request.data.get("target_type") or "").strip().lower()
        target_id = (request.data.get("target_id") or "").strip()
        new_password = request.data.get("new_password") or ""
        confirm_new_password = request.data.get("confirm_new_password") or ""

        if not target_type or not target_id or not new_password or not confirm_new_password:
            return _err("target_type, target_id, new_password, and confirm_new_password are required.")

        if new_password != confirm_new_password:
            return _err("Passwords do not match.")

        complexity_error = _validate_password_complexity(new_password)
        if complexity_error:
            return _err(complexity_error)

        if target_type == "staff":
            try:
                staff = Staffcreation.objects.get(staff_unique_id=target_id, is_deleted=False)
            except Staffcreation.DoesNotExist:
                return _err("Staff member not found.", status.HTTP_404_NOT_FOUND)

            staff.previous_password = staff.password
            staff.password = encrypt_password(new_password)
            staff.password_crt_date = timezone.now()
            staff.save(update_fields=["password", "previous_password", "password_crt_date"])
            return _ok("Staff password updated successfully.")

        elif target_type == "customer":
            try:
                customer = CustomerCreation.objects.get(unique_id=target_id, is_deleted=False)
            except CustomerCreation.DoesNotExist:
                return _err("Customer not found.", status.HTTP_404_NOT_FOUND)

            customer.previous_password = customer.password
            customer.password = make_password(new_password)
            customer.password_crt_date = timezone.now()
            customer.save(update_fields=["password", "previous_password", "password_crt_date"])
            return _ok("Customer password updated successfully.")

        return _err("target_type must be 'staff' or 'customer'.")

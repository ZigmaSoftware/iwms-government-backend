import re
import uuid
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from app.models.customers.customercreation import CustomerCreation
from app.models.customers.password_reset_otp import PasswordResetOTP
from app.utils.email_utils import send_otp_email


def _validate_password_complexity(password: str):
    """Return an error message string if the password fails complexity rules, else None."""
    if len(password) < 6:
        return "Password must be at least 6 characters."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one numeric digit."
    return None


def _generic_ok(msg: str, data: dict = None):
    payload = {"success": True, "message": msg}
    if data:
        payload.update(data)
    return Response(payload, status=status.HTTP_200_OK)


def _err(msg: str, code=status.HTTP_400_BAD_REQUEST):
    return Response({"success": False, "message": msg}, status=code)


class ForgotPasswordView(APIView):
    """
    POST /api/v1/auth/forgot-password
    Body: { "username": "...", "email": "..." }

    Validates that the username + email belong to the same customer,
    generates a 4-digit OTP, stores it, and sends it via email.
    Returns a session_token the client must include in the verify-otp call.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        email = (request.data.get("email") or "").strip().lower()

        if not username or not email:
            return _err("Username and email are required.")

        # Always return the same generic message to prevent enumeration attacks
        GENERIC_MSG = "If the details are correct, an OTP has been sent to your email."

        try:
            customer = CustomerCreation.objects.get(
                username=username,
                is_deleted=False,
            )
        except CustomerCreation.DoesNotExist:
            return _generic_ok(GENERIC_MSG)

        stored_email = (customer.email or "").strip().lower()
        if stored_email != email:
            return _generic_ok(GENERIC_MSG)

        # Rate limit: max N OTP requests in the last X minutes
        window_minutes = getattr(settings, 'OTP_RATE_WINDOW_MINUTES', 10)
        max_requests = getattr(settings, 'OTP_MAX_REQUESTS_PER_WINDOW', 3)
        since = timezone.now() - timezone.timedelta(minutes=window_minutes)
        recent_count = PasswordResetOTP.objects.filter(
            customer=customer,
            created_at__gte=since,
        ).count()
        if recent_count >= max_requests:
            return _err(
                f"Too many OTP requests. Please wait {window_minutes} minutes before trying again.",
                status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Resend cooldown: must wait N minutes since last OTP
        cooldown = getattr(settings, 'OTP_RESEND_COOLDOWN_MINUTES', 2)
        cooldown_since = timezone.now() - timezone.timedelta(minutes=cooldown)
        last_otp = PasswordResetOTP.objects.filter(
            customer=customer,
            created_at__gte=cooldown_since,
            is_used=False,
        ).first()
        if last_otp:
            wait_seconds = int((last_otp.created_at + timezone.timedelta(minutes=cooldown) - timezone.now()).total_seconds())
            if wait_seconds > 0:
                return _err(
                    f"Please wait {wait_seconds} seconds before requesting a new OTP.",
                    status.HTTP_429_TOO_MANY_REQUESTS,
                )

        # Invalidate all previous unused OTPs for this customer
        PasswordResetOTP.objects.filter(customer=customer, is_used=False).update(is_used=True)

        otp_record = PasswordResetOTP.create_for_customer(customer)
        sent = send_otp_email(
            recipient_email=customer.email,
            otp_code=otp_record.otp_code,
            username=username,
        )

        if not sent:
            otp_record.delete()
            return _err("Failed to send OTP email. Please try again later.", status.HTTP_500_INTERNAL_SERVER_ERROR)

        return _generic_ok(GENERIC_MSG, {"session_token": str(otp_record.session_token)})


class VerifyOTPView(APIView):
    """
    POST /api/v1/auth/verify-otp
    Body: { "session_token": "...", "otp_code": "..." }

    Verifies the OTP. On success returns a one-time reset_token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        session_token = (request.data.get("session_token") or "").strip()
        otp_code = (request.data.get("otp_code") or "").strip()

        if not session_token or not otp_code:
            return _err("session_token and otp_code are required.")

        try:
            otp_record = PasswordResetOTP.objects.select_related("customer").get(
                session_token=session_token,
            )
        except PasswordResetOTP.DoesNotExist:
            return _err("Invalid session. Please request a new OTP.")

        max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 3)

        if otp_record.is_used:
            return _err("OTP has already been used. Please request a new one.")

        if otp_record.is_expired():
            return _err("OTP has expired. Please request a new one.")

        if otp_record.attempts >= max_attempts:
            otp_record.is_used = True
            otp_record.save(update_fields=["is_used"])
            return _err("Too many incorrect attempts. Please request a new OTP.")

        if otp_record.otp_code != otp_code:
            otp_record.attempts += 1
            otp_record.save(update_fields=["attempts"])
            remaining = max_attempts - otp_record.attempts
            return _err(f"Incorrect OTP. {remaining} attempt(s) remaining.")

        # OTP is correct — generate a reset token
        otp_record.reset_token = uuid.uuid4()
        # Do NOT mark is_used yet — reset-password will do that
        otp_record.save(update_fields=["reset_token"])

        return _generic_ok("OTP verified successfully.", {"reset_token": str(otp_record.reset_token)})


class ResetPasswordView(APIView):
    """
    POST /api/v1/auth/reset-password
    Body: { "reset_token": "...", "new_password": "...", "confirm_password": "..." }

    Resets the customer's password. Invalidates the OTP afterwards.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        reset_token = (request.data.get("reset_token") or "").strip()
        new_password = request.data.get("new_password") or ""
        confirm_password = request.data.get("confirm_password") or ""

        if not reset_token or not new_password or not confirm_password:
            return _err("reset_token, new_password, and confirm_password are required.")

        if new_password != confirm_password:
            return _err("Passwords do not match.")

        complexity_error = _validate_password_complexity(new_password)
        if complexity_error:
            return _err(complexity_error)

        try:
            otp_record = PasswordResetOTP.objects.select_related("customer").get(
                reset_token=reset_token,
            )
        except PasswordResetOTP.DoesNotExist:
            return _err("Invalid or expired reset token.")

        if otp_record.is_used:
            return _err("Reset token has already been used.")

        if otp_record.is_expired():
            return _err("Reset token has expired. Please start over.")

        customer = otp_record.customer

        # Prevent reuse of the current password
        if customer.password and check_password(new_password, customer.password):
            return _err("New password must be different from the current password.")

        # Store previous password before updating
        previous_password = customer.password
        customer.previous_password = previous_password
        customer.password = make_password(new_password)
        customer.password_crt_date = timezone.now()
        customer.save(update_fields=["password", "previous_password", "password_crt_date"])

        # Invalidate the OTP so it cannot be reused
        otp_record.is_used = True
        otp_record.save(update_fields=["is_used"])

        return _generic_ok("Password reset successfully. You can now log in with your new password.")

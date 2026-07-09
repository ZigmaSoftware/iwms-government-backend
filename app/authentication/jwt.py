import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from app.models.user_creations.staffcreation import Staffcreation
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat_leader_login import PanchayatLeaderLogin


class JWTUserAuthentication(BaseAuthentication):
    """
    Resolve a user from the Bearer token.
    Supports both Staff (Staffcreation) and Customer (CustomerCreation) authentication.
    """

    def authenticate(self, request):
        raw_request = getattr(request, "_request", None)
        existing_user = getattr(raw_request, "user", None)
        
        # Check if already authenticated via other means
        if hasattr(existing_user, 'staff_unique_id'):
            return (existing_user, None)
        if hasattr(existing_user, 'unique_id') and hasattr(existing_user, 'customer_name'):
            return (existing_user, None)

        auth = request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return None

        token = auth.split(" ", 1)[1].strip()
        # Remove all whitespace characters including newlines from the token
        token = ''.join(token.split())
        if not token:
            return None

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationFailed("Token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationFailed("Invalid token") from exc

        unique_id = payload.get("unique_id")
        if not unique_id:
            raise AuthenticationFailed("Invalid token")

        # Try to find user in Staffcreation first (uses staff_unique_id)
        staff = Staffcreation.objects.filter(staff_unique_id=unique_id).first()
        if staff:
            if not staff.login_enabled:
                raise AuthenticationFailed("Login is disabled for this user")
            request.jwt_payload = payload
            return (staff, None)
        
        # Try to find user in CustomerCreation (uses unique_id)
        customer = CustomerCreation.objects.filter(unique_id=unique_id).first()
        if customer:
            request.jwt_payload = payload
            return (customer, None)

        # Try to find user in PanchayatLeaderLogin (uses unique_id with prefix PLDR-)
        leader = PanchayatLeaderLogin.objects.select_related(
            "panchayat_id"
        ).filter(unique_id=unique_id).first()
        if leader:
            request.jwt_payload = payload
            return (leader, None)

        # Fall back to Django User (platform super admin)
        UserModel = get_user_model()
        user = UserModel.objects.filter(unique_id=unique_id).first()
        if not user:
            user_id = payload.get("user_id")
            if user_id:
                user = UserModel.objects.filter(pk=user_id).first()
        if user:
            request.jwt_payload = payload
            return (user, None)

        raise AuthenticationFailed("User not found")

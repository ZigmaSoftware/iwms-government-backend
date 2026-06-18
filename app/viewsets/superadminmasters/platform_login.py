from django.contrib.auth import authenticate
from django.contrib.auth.hashers import check_password
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import AccessToken

from app.serializers.superadmin_masters.platform_login_serializer import PlatformLoginSerializer
from app.models.user_creations.staffcreation import Staffcreation


@method_decorator(csrf_exempt, name='dispatch')
class PlatformLoginView(APIView):
    permission_classes = [AllowAny]

    def _password_matches(self, raw_password, stored_password):
        """Check if raw password matches stored password."""
        from django.contrib.auth.hashers import identify_hasher
        if stored_password is None:
            return False
        try:
            identify_hasher(stored_password)
        except ValueError:
            return raw_password == stored_password
        return check_password(raw_password, stored_password)

    def post(self, request):
        serializer = PlatformLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"].strip()
        password = serializer.validated_data["password"].strip()

        # Try Staffcreation first
        staff = Staffcreation.objects.filter(
            username__iexact=username,
            is_active=True,
            is_deleted=False,
            is_superuser=True,
        ).first()

        if staff:
            if not self._password_matches(password, staff.password):
                raise AuthenticationFailed("Invalid username or password")

            access = AccessToken.for_user(staff)
            access["unique_id"] = staff.staff_unique_id
            access["username"] = staff.username
            access["platform"] = True

            return Response(
                {
                    "access_token": str(access),
                    "unique_id": staff.staff_unique_id,
                    "username": staff.username,
                },
                status=status.HTTP_200_OK,
            )

        # Fall back to Django User (for superusers created via createsuperuser)
        user = authenticate(request=request, username=username, password=password)
        if user:
            if not getattr(user, "is_superuser", False):
                raise PermissionDenied("Not a platform super admin")

            access = AccessToken.for_user(user)
            access["unique_id"] = getattr(user, "unique_id", None) or str(user.pk)
            access["username"] = user.username
            access["platform"] = True

            return Response(
                {
                    "access_token": str(access),
                    "unique_id": getattr(user, "unique_id", None) or str(user.pk),
                    "username": user.username,
                },
                status=status.HTTP_200_OK,
            )

        raise AuthenticationFailed("Invalid username or password")

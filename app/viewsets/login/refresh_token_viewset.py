from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

# Identity claims minted onto both the access and refresh token at login
# (see login_viewset.py) — copied verbatim onto the newly minted access
# token so a refresh behaves exactly like the original login for anything
# that reads the token payload (JWTUserAuthentication, ModulePermissionMiddleware).
IDENTITY_CLAIMS = (
    "unique_id",
    "user_type",
    "name",
    "role",
    "email",
    "staff_config_name",
    "emp_id",
    "employee_id",
)


class RefreshTokenViewSet(ViewSet):
    """
    Exchanges a still-valid refresh token for a fresh access token, so the
    frontend can renew an expired session silently instead of forcing the
    user back to the login screen.
    """

    permission_classes = [AllowAny]

    def create(self, request):
        """
        POST /api/v1/login/refresh-token/
        Body: {"refresh": "<refresh_token>"}
        """
        raw_refresh = (request.data.get("refresh") or "").strip()
        if not raw_refresh:
            return Response(
                {"detail": "refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(raw_refresh)
        except TokenError as exc:
            return Response(
                {"detail": str(exc) or "Refresh token invalid or expired"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        access = AccessToken()
        for claim in IDENTITY_CLAIMS:
            if claim in refresh:
                access[claim] = refresh[claim]

        iat = access["iat"]
        exp = access["exp"]
        access["valid_seconds"] = exp - iat
        access["valid_hours"] = round((exp - iat) / 3600, 2)
        access["valid_days"] = round((exp - iat) / 86400, 4)

        return Response(
            {
                "access_token": str(access),
                "token_type": "Bearer",
                "expires_in": exp - iat,
            },
            status=status.HTTP_200_OK,
        )

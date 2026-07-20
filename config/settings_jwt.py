import os
from datetime import timedelta

SIMPLE_JWT = {
    # Access token used on every request (5 hours)
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=5),

    # Refresh token lets the frontend silently mint a new access token
    # without forcing a re-login. Longer-lived than the access token by
    # design — see app/viewsets/login/refresh_token_viewset.py.
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,

    "UPDATE_LAST_LOGIN": False,

    "ALGORITHM": "HS256",
    "SIGNING_KEY": os.getenv("SECRET_KEY", ""),
    "AUTH_HEADER_TYPES": ("Bearer",),
    # Use pk so tokens can be minted for both Staffcreation and User
    # (their primary keys differ, but pk always resolves correctly).
    "USER_ID_FIELD": "pk",
}

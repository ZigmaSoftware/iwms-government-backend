import os
from datetime import timedelta

SIMPLE_JWT = {
    # ONLY Access Token (5 hours)
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=5),

    # Disable refresh tokens
    "REFRESH_TOKEN_LIFETIME": timedelta(seconds=1),  # expires immediately
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

"""Firebase Cloud Messaging (FCM) push notifications.

This is intentionally self-gating: if `FIREBASE_CREDENTIALS_PATH` isn't set, or
the file it points to doesn't exist, or `firebase-admin` isn't installed, every
call here becomes a safe no-op (logged once, not raised). This means the rest
of the app — waste collection, status updates, etc. — never breaks because
push isn't configured yet. Once a real Firebase service-account JSON is in
place and the env var points to it, sending "just works" with no other code
changes.

Setup (one-time, ops side):
  1. Create/choose a Firebase project whose registered Android/iOS app package
     name matches this app's `applicationId` / bundle id.
  2. Firebase Console -> Project settings -> Service accounts -> Generate new
     private key. Save the JSON somewhere NOT committed to the repo.
  3. Set `FIREBASE_CREDENTIALS_PATH=/path/to/service-account.json` in .env.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

_firebase_app = None
_init_attempted = False


def _get_firebase_app():
    """Lazily initialize the Firebase Admin app. Returns None (and logs once)
    if push isn't configured or the SDK isn't installed."""
    global _firebase_app, _init_attempted
    if _firebase_app is not None:
        return _firebase_app
    if _init_attempted:
        return None
    _init_attempted = True

    credentials_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", "") or ""
    if not credentials_path:
        logger.info(
            "[push] FIREBASE_CREDENTIALS_PATH not set — push notifications are "
            "disabled until Firebase is configured."
        )
        return None

    try:
        import os
        if not os.path.isfile(credentials_path):
            logger.warning(
                "[push] FIREBASE_CREDENTIALS_PATH=%s does not exist — push "
                "notifications disabled.", credentials_path,
            )
            return None

        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(credentials_path)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("[push] Firebase Admin initialized for push notifications.")
        return _firebase_app
    except ImportError:
        logger.warning(
            "[push] firebase-admin is not installed — push notifications "
            "disabled. Run `pip install firebase-admin` and add it to "
            "requirements.txt."
        )
        return None
    except Exception:
        logger.exception("[push] Failed to initialize Firebase Admin.")
        return None


def send_push_to_customer(customer, title, body, data=None):
    """Send a push notification to a single customer's registered device.

    Safe to call unconditionally from any code path (signals, viewsets): it
    never raises. Returns True if a message was actually sent, False otherwise
    (no token, push not configured, or the send failed).
    """
    if customer is None:
        return False

    token = getattr(customer, "fcm_token", None)
    if not token:
        return False

    app = _get_firebase_app()
    if app is None:
        return False

    try:
        from firebase_admin import messaging

        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data={str(k): str(v) for k, v in (data or {}).items()},
            android=messaging.AndroidConfig(
                notification=messaging.AndroidNotification(
                    channel_id="iwms_default_channel",
                ),
            ),
        )
        messaging.send(message, app=app)
        return True
    except Exception:
        logger.exception(
            "[push] Failed to send push to customer %s",
            getattr(customer, "unique_id", customer),
        )
        return False

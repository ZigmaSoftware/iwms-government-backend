"""Firebase Cloud Messaging (FCM) push notifications.

This is intentionally self-gating: if `FIREBASE_CREDENTIALS_PATH` isn't set, or
the file it points to doesn't exist, or `firebase-admin` isn't installed, every
call here becomes a safe no-op (logged once, not raised). This means the rest
of the app — waste collection, status updates, etc. — never breaks because
push isn't configured yet. Once a real Firebase service-account JSON is in
place and the env var points to it, sending "just works" with no other code
changes.

Sends are queued to Celery (`send_push_task` in app/tasks/notification_tasks.py)
so a slow or unreachable Firebase never delays the API request that triggered
the notification; transient Firebase failures are retried there.

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
    """Queue a push notification to a single customer's registered device.

    Safe to call unconditionally from any code path (signals, viewsets): it
    never raises and never waits on Firebase — the send runs on a Celery
    worker after the current transaction commits. Returns True if a push was
    queued, False when there is nothing to send (no token, push not
    configured).
    """
    if customer is None:
        return False
    return _queue_push(
        getattr(customer, "fcm_token", None), title, body, data,
        recipient=f"customer {getattr(customer, 'unique_id', customer)}",
    )


def send_push_to_staff(staff, title, body, data=None):
    """Queue a push notification to a single staff member's registered device
    (driver/operator/supervisor apps). Same contract as
    `send_push_to_customer`.
    """
    if staff is None:
        return False
    return _queue_push(
        getattr(staff, "fcm_token", None), title, body, data,
        recipient=f"staff {getattr(staff, 'staff_unique_id', staff)}",
    )


def _queue_push(token, title, body, data, recipient):
    if not token or not getattr(settings, "FIREBASE_CREDENTIALS_PATH", ""):
        return False

    from app.tasks import enqueue_on_commit
    from app.tasks.notification_tasks import send_push_task

    enqueue_on_commit(
        send_push_task, token, str(title), str(body),
        {str(k): str(v) for k, v in (data or {}).items()},
        recipient,
    )
    return True


def deliver_push(token, title, body, data):
    """Send one FCM message now. Called by `send_push_task` on the Celery
    worker. Returns False if push isn't configured; raises if the send
    fails so the task can retry transient Firebase errors."""
    app = _get_firebase_app()
    if app is None:
        return False

    from firebase_admin import messaging

    message = messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=body),
        data=data,
        android=messaging.AndroidConfig(
            notification=messaging.AndroidNotification(
                channel_id="iwms_default_channel",
            ),
        ),
    )
    messaging.send(message, app=app)
    return True


def is_transient_push_error(exc):
    """True for Firebase errors worth retrying (outage/timeout), False for
    permanent ones such as an unregistered token."""
    try:
        from firebase_admin import exceptions
    except ImportError:
        return False
    return isinstance(
        exc,
        (exceptions.UnavailableError, exceptions.InternalError, exceptions.DeadlineExceededError),
    )

from django.db import models

from app.utils.comfun import generate_unique_id


def generate_login_id():
    return f"LOGINAUDIT-{generate_unique_id()}"


class LoginAudit(models.Model):

    unique_id = models.CharField(
        max_length=100,
        primary_key=True,
        default=generate_login_id,
        editable=False,
    )

    user_unique_id = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    # Authentication provider/module that handled the attempt (for example
    # staff, government, customer, platform, or a leader login).
    module_name = models.CharField(max_length=50, default="auto", db_index=True)

    username = models.CharField(max_length=150)
    password = models.CharField(max_length=150, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    success = models.BooleanField()
    reason = models.CharField(max_length=255, null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    # -------------------------
    # SESSION TRACKING
    # -------------------------
    # A successful login row doubles as the session record: the access and
    # refresh tokens carry this row's unique_id as `login_audit_id`, so
    # logout / idle timeout can be stamped back onto the same login.
    LOGOUT_MANUAL = "manual"
    LOGOUT_IDLE_TIMEOUT = "idle_timeout"
    LOGOUT_TOKEN_EXPIRED = "token_expired"
    LOGOUT_TYPE_CHOICES = [
        (LOGOUT_MANUAL, "Manual Logout"),
        (LOGOUT_IDLE_TIMEOUT, "Auto Logout (Idle)"),
        (LOGOUT_TOKEN_EXPIRED, "Session Expired"),
    ]

    # Null for sessions with no idle limit (e.g. mobile app logins).
    idle_timeout_seconds = models.PositiveIntegerField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    logout_at = models.DateTimeField(null=True, blank=True)
    logout_type = models.CharField(
        max_length=20, choices=LOGOUT_TYPE_CHOICES, null=True, blank=True
    )
    session_duration_seconds = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    @property
    def used_hours(self):
        """Session length as HH:MM:SS, or None while the session is open."""
        if self.session_duration_seconds is None:
            return None
        hours, rem = divmod(self.session_duration_seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

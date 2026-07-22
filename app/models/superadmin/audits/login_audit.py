from django.db import models

from app.models.user_creations.loginAudit import generate_login_id


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

    username = models.CharField(max_length=150)
    password = models.CharField(max_length=150, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    success = models.BooleanField()
    reason = models.CharField(max_length=255, null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

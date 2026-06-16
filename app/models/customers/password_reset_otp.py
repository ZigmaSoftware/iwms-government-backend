import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings


class PasswordResetOTP(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        'app.CustomerCreation',
        on_delete=models.CASCADE,
        related_name='password_reset_otps',
        db_column='customer_id',
    )
    otp_code = models.CharField(max_length=6)
    # Opaque token returned to the client after OTP send; used to scope verify/reset calls
    session_token = models.UUIDField(default=uuid.uuid4, unique=True)
    # Opaque token returned after OTP verification; required for reset-password call
    reset_token = models.UUIDField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def is_expired(self):
        return timezone.now() > self.expires_at

    def is_valid(self):
        return not self.is_used and not self.is_expired()

    @classmethod
    def create_for_customer(cls, customer):
        import random
        expiry = timezone.now() + timezone.timedelta(
            minutes=getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
        )
        otp_code = f"{random.randint(1000, 9999)}"
        return cls.objects.create(
            customer=customer,
            otp_code=otp_code,
            expires_at=expiry,
        )

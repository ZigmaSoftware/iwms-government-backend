from django.db import models

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_customer_notification_id():
    return f"CUSTNOTIF-{generate_unique_id()}"


class CustomerNotification(BaseMaster):
    """Testing list for sending a sample collection push to customers."""

    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_customer_notification_id,
        editable=False,
    )
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.CASCADE,
        related_name="test_notifications",
        to_field="unique_id",
        db_column="customer_id",
    )
    last_tested_at = models.DateTimeField(null=True, blank=True)
    last_test_sent = models.BooleanField(default=False)
    last_test_message = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["customer__customer_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer"],
                condition=models.Q(is_deleted=False),
                name="uq_active_customer_notification",
            )
        ]

    def __str__(self):
        return str(self.customer)

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])

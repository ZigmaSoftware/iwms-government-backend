"""Per-customer app access.

Customers are not staff, so they have no StaffAccessConfiguration to hang
grants off. They also have no web screens: every citizen API route is
middleware-exempt and hard-scoped to the logged-in customer inside the
viewset, so there is nothing in the ordinary permission catalog to grant them.

That makes this the one deliberate exception to "one permission list": a
customer's configuration holds the app modules they may sign into, plus the
citizen app screens they can see. Those screen ticks gate the app's UI only —
they authorize nothing at the API, because the citizen routes need no
authorization beyond being signed in as that customer.
"""

from django.db import models
from django.db.models import UniqueConstraint

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.screen_management.app_module import AppModule
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_customer_access_configuration_id():
    return f"CUSTACCCFG-{generate_unique_id()}"


class CustomerAccessConfiguration(BaseMaster):
    unique_id = models.CharField(
        max_length=60,
        primary_key=True,
        unique=True,
        default=generate_customer_access_configuration_id,
        editable=False,
    )

    customer_id = models.ForeignKey(
        CustomerCreation,
        on_delete=models.CASCADE,
        to_field="unique_id",
        db_column="customer_id",
        related_name="access_configuration",
    )

    # Apps this customer may sign into. No module ticked = mobile login refused.
    app_modules = models.ManyToManyField(
        AppModule,
        related_name="customer_access_configurations",
        blank=True,
    )

    # Citizen app screens this customer can see. UI gating only.
    app_screens = models.ManyToManyField(
        UserScreen,
        related_name="customer_access_configurations",
        blank=True,
    )

    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            UniqueConstraint(
                fields=["customer_id"],
                condition=models.Q(is_deleted=False),
                name="uq_active_customer_access_configuration",
            )
        ]

    def __str__(self):
        return f"{self.customer_id_id}"

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])

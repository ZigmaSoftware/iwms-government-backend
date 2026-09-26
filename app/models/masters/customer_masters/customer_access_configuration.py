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
from app.utils import ref_cache


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

    # Plain CustomerCreation unique_id (no DB relation).
    customer_id = models.CharField(max_length=30, db_column="customer_id", db_index=True)

    # Apps this customer may sign into (AppModule unique_ids). No module
    # ticked = mobile login refused.
    app_module_ids = models.JSONField(default=list, blank=True)

    # Citizen app screens this customer can see (UserScreen unique_ids). UI
    # gating only.
    app_screen_ids = models.JSONField(default=list, blank=True)

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
        return f"{self.customer_id}"

    @property
    def customer(self):
        return ref_cache.get(CustomerCreation, self.customer_id, "unique_id")

    @property
    def app_modules(self):
        """AppModule QuerySet for `app_module_ids`."""
        return AppModule.objects.filter(unique_id__in=self.app_module_ids or [])

    @property
    def app_screens(self):
        """UserScreen QuerySet for `app_screen_ids`."""
        return UserScreen.objects.filter(unique_id__in=self.app_screen_ids or [])

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])

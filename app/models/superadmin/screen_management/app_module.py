"""The mobile app modules a user can be granted access to.

One row per app in the Flutter build. This is a master rather than a code
constant so the label and ordering shown in web can be maintained without a
release — but `module_key`, `surface_key` and `route` stay read-only, because
each module is backed by screens and routes that ship inside the mobile app.
A module invented in web would appear in every dropdown and route nowhere.

Access is granted by ticking a module on a StaffAccessConfiguration (or a
CustomerAccessConfiguration). That tick decides whether the person may sign
into that app at all; what they can do once inside comes from the ordinary
screen permissions, which are the same rows that govern web.
"""

from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_app_module_id():
    return f"APPMOD-{generate_unique_id()}"


class AppModule(BaseMaster):
    unique_id = models.CharField(
        max_length=40,
        primary_key=True,
        unique=True,
        default=generate_app_module_id,
        editable=False,
    )

    # Stable identifier used by the backend and the app. Never edited in web.
    module_key = models.CharField(max_length=40, unique=True, editable=False)

    # What the mobile app routes on ("driver", "supervisor", ...).
    surface_key = models.CharField(max_length=20, unique=True, editable=False)

    label = models.CharField(max_length=60)
    route = models.CharField(max_length=120, editable=False)
    order_no = models.IntegerField(default=0)
    description = models.CharField(max_length=255, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order_no", "label"]

    def __str__(self):
        return self.label

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.is_deleted = True
        self.save(update_fields=["is_active", "is_deleted"])

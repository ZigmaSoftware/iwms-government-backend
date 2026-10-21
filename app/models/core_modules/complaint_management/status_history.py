from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_status_history_id():
    return f"CPTSH-{generate_unique_id()}"


class ComplaintStatusHistory(BaseMaster):
    """Audit row written on every ticket status change."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_status_history_id,
        editable=False,
    )

    ticket_id = models.CharField(db_index=True, max_length=30)
    from_status_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    to_status_id = models.CharField(db_index=True, max_length=30)
    changed_by_user_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    changed_by_customer_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    changed_by_system = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)
    visible_to_citizen = models.BooleanField(default=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Complaint Status History"
        verbose_name_plural = "Complaint Status History"

    def __str__(self):
        return f"{self.ticket_id}: {self.to_status_id}"

    def _lookup(self, model_path, value, field="unique_id"):
        if not value:
            return None
        import importlib

        module_path, class_name = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(module_path), class_name)
        return ref_cache.get(model, value, field)

    @property
    def ticket(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.ticket.ComplaintTicket",
            self.ticket_id,
        )

    @property
    def from_status(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.status_master.ComplaintStatus",
            self.from_status_id,
        )

    @property
    def to_status(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.status_master.ComplaintStatus",
            self.to_status_id,
        )

    @property
    def changed_by_user(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User",
            self.changed_by_user_id,
        )

    @property
    def changed_by_customer(self):
        return self._lookup(
            "app.models.masters.customer_masters.customercreation.CustomerCreation",
            self.changed_by_customer_id,
        )

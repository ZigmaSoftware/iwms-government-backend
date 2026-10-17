from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_reopen_history_id():
    return f"CPTRO-{generate_unique_id()}"


class ComplaintReopenHistory(BaseMaster):
    """Audit row written each time a ticket is reopened."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_reopen_history_id,
        editable=False,
    )

    ticket_id = models.CharField(db_index=True, max_length=30)
    reopened_by_customer_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    reopened_by_user_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    reopen_reason = models.TextField(blank=True, null=True)
    previous_status_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)

    reopened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reopened_at"]
        verbose_name = "Complaint Reopen History"
        verbose_name_plural = "Complaint Reopen History"

    def __str__(self):
        return f"{self.ticket_id} reopened"

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
    def reopened_by_customer(self):
        return self._lookup(
            "app.models.masters.customer_masters.customercreation.CustomerCreation",
            self.reopened_by_customer_id,
        )

    @property
    def reopened_by_user(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User",
            self.reopened_by_user_id,
        )

    @property
    def previous_status(self):
        return self._lookup(
            "app.models.core_modules.complaint_management.status_master.ComplaintStatus",
            self.previous_status_id,
        )

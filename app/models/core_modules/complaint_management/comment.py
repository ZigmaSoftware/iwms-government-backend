from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_comment_id():
    return f"CPTCMT-{generate_unique_id()}"


class ComplaintComment(BaseMaster):
    """Comments / notes on a complaint ticket (internal or citizen-facing)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_comment_id,
        editable=False,
    )

    ticket_id = models.CharField(db_index=True, max_length=30)
    comment_by_user_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    comment_by_customer_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    comment_text = models.TextField()
    is_internal = models.BooleanField(default=False)
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Comment"
        verbose_name_plural = "Complaint Comments"

    def __str__(self):
        return f"{self.ticket_id} comment {self.unique_id}"

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
    def comment_by_user(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User", self.comment_by_user_id
        )

    @property
    def comment_by_customer(self):
        return self._lookup(
            "app.models.masters.customer_masters.customercreation.CustomerCreation",
            self.comment_by_customer_id,
        )

from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_feedback_id():
    return f"CPTFB-{generate_unique_id()}"


class ComplaintFeedback(BaseMaster):
    """Citizen feedback captured after resolution (one per ticket)."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_feedback_id,
        editable=False,
    )

    ticket_id = models.CharField(max_length=30, unique=True)
    customer_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    rating = models.IntegerField(null=True, blank=True)
    feedback_text = models.TextField(blank=True, null=True)
    is_issue_solved = models.BooleanField(default=False)

    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Complaint Feedback"
        verbose_name_plural = "Complaint Feedback"

    def __str__(self):
        return f"{self.ticket_id} feedback {self.rating}"

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
    def customer(self):
        return self._lookup(
            "app.models.masters.customer_masters.customercreation.CustomerCreation",
            self.customer_id,
        )

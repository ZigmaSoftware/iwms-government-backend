from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_attachment_id():
    return f"CPTATT-{generate_unique_id()}"


def complaint_attachment_upload_path(instance, filename):
    return f"uploads/complaint_ticket/{instance.ticket_id}_{filename}"


class ComplaintAttachment(BaseMaster):
    """File attachments for a complaint ticket."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_attachment_id,
        editable=False,
    )

    ticket_id = models.CharField(db_index=True, max_length=30)
    uploaded_by_customer_id = models.CharField(db_index=True, max_length=30, null=True, blank=True)
    uploaded_by_user_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)

    file = models.FileField(upload_to=complaint_attachment_upload_path, null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_type = models.CharField(max_length=50, blank=True, null=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Attachment"
        verbose_name_plural = "Complaint Attachments"

    def __str__(self):
        return self.file_name or self.unique_id

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
    def uploaded_by_customer(self):
        return self._lookup(
            "app.models.masters.customer_masters.customercreation.CustomerCreation",
            self.uploaded_by_customer_id,
        )

    @property
    def uploaded_by_user(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User",
            self.uploaded_by_user_id,
        )

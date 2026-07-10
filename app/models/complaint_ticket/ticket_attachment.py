from django.conf import settings
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.customers.customercreation import CustomerCreation
from app.models.complaint_ticket.ticket import ComplaintTicket


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

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by_customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_attachments",
    )
    uploaded_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_attachments",
    )

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

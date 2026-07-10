from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.complaint_ticket.ticket import ComplaintTicket


def generate_extra_detail_id():
    return f"CPTXTRA-{generate_unique_id()}"


class ComplaintTicketExtraDetail(BaseMaster):
    """Category-specific dynamic key/value fields for a ticket."""

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_extra_detail_id,
        editable=False,
    )

    ticket = models.ForeignKey(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="extra_details",
    )
    field_key = models.CharField(max_length=100)
    field_value = models.TextField(blank=True, null=True)
    field_type = models.CharField(max_length=50, default="text")
    is_sensitive = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Ticket Extra Detail"
        verbose_name_plural = "Complaint Ticket Extra Details"

    def __str__(self):
        return f"{self.field_key}={self.field_value}"

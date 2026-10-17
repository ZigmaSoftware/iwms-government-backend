from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_cleanup_report_id():
    return f"CPTCLN-{generate_unique_id()}"


class ComplaintCleanupReport(BaseMaster):
    """A citizen's "Verify Cleanup" from the public complaint map: a photo of
    the cleaned spot waiting for the officer the ticket currently sits with.
    Approving it closes the ticket; rejecting it leaves the ticket open (and
    lets citizens report again). One PENDING report per ticket at a time."""

    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_cleanup_report_id,
        editable=False,
    )

    ticket_id = models.CharField(db_index=True, max_length=30)
    # ComplaintAttachment holding the photo (file_type "cleanup_proof")
    attachment_id = models.CharField(max_length=30)
    note = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)

    # Who reviewed it: a staff login (staff_unique_id) or an admin auth user.
    reviewed_by_staff_id = models.CharField(max_length=30, null=True, blank=True)
    reviewed_by_user_id = models.CharField(max_length=100, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_remarks = models.TextField(blank=True, null=True)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Cleanup Report"
        verbose_name_plural = "Complaint Cleanup Reports"

    def __str__(self):
        return f"{self.ticket_id} cleanup {self.status}"

    @property
    def attachment(self):
        from app.models.core_modules.complaint_management.ticket_attachment import ComplaintAttachment

        return ComplaintAttachment.objects.filter(unique_id=self.attachment_id).first()

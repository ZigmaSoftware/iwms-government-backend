from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.utils import ref_cache


def generate_address_change_id():
    return f"CPTADRC-{generate_unique_id()}"


class ComplaintAddressChangeRequest(BaseMaster):
    """Change-Address request linked 1:1 to a ticket.

    On approval the linked CustomerCreation address is overwritten in place
    (no address-history table per project decision).
    """

    class ChangeType(models.TextChoices):
        SERVICE_ADDRESS_CHANGE = "SERVICE_ADDRESS_CHANGE", "Service Address Change"
        BILLING_ADDRESS_CHANGE = "BILLING_ADDRESS_CHANGE", "Billing Address Change"
        ADDRESS_CORRECTION = "ADDRESS_CORRECTION", "Address Correction"
        WARD_ROUTE_CHANGE = "WARD_ROUTE_CHANGE", "Ward / Route Change"

    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    class ProofType(models.TextChoices):
        AADHAAR = "AADHAAR_ADDRESS_PROOF", "Aadhaar Address Proof"
        EB_BILL = "EB_BILL", "Electricity Bill"
        WATER_TAX = "WATER_TAX_RECEIPT", "Water Tax Receipt"
        PROPERTY_TAX = "PROPERTY_TAX_RECEIPT", "Property Tax Receipt"
        RENT_AGREEMENT = "RENT_AGREEMENT", "Rent Agreement"
        OWNER_DECLARATION = "OWNER_DECLARATION", "Owner Declaration"
        OTHER = "OTHER_PROOF", "Other Proof"

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_address_change_id,
        editable=False,
    )

    ticket_id = models.CharField(max_length=30, unique=True)
    customer_id = models.CharField(db_index=True, max_length=30)

    change_type = models.CharField(
        max_length=40,
        choices=ChangeType.choices,
        default=ChangeType.SERVICE_ADDRESS_CHANGE,
    )
    old_address_snapshot = models.JSONField(null=True, blank=True)

    # Requested new address values
    new_building_no = models.CharField(max_length=20, null=True, blank=True)
    new_street = models.CharField(max_length=100, null=True, blank=True)
    new_area = models.CharField(max_length=50, null=True, blank=True)
    new_landmark = models.CharField(max_length=200, null=True, blank=True)
    new_pincode = models.CharField(max_length=10, null=True, blank=True)
    new_latitude = models.CharField(max_length=100, null=True, blank=True)
    new_longitude = models.CharField(max_length=100, null=True, blank=True)
    new_full_address = models.TextField(null=True, blank=True)

    # Requested new flat geo (same family as CustomerCreation). Only one of
    # the local-body fields should be populated at a time. Plain CharFields
    # holding the related row's `unique_id` (no DB relation/join) — same
    # convention as Ward/CustomerCreation and the rest of the geo-hierarchy
    # refactor, kept "new_"-prefixed to match this model's own naming.
    new_state_id = models.CharField(max_length=30, null=True, blank=True)
    new_district_id = models.CharField(max_length=30, null=True, blank=True)
    new_area_type_id = models.CharField(max_length=30, null=True, blank=True)
    new_corporation_id = models.CharField(max_length=30, null=True, blank=True)
    new_municipality_id = models.CharField(max_length=30, null=True, blank=True)
    new_town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    new_panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    new_panchayat_id = models.CharField(max_length=30, null=True, blank=True)

    proof_type = models.CharField(
        max_length=40,
        choices=ProofType.choices,
        null=True,
        blank=True,
    )
    proof_file = models.FileField(
        upload_to="uploads/complaint_ticket/address_change/",
        null=True,
        blank=True,
    )
    requested_effective_date = models.DateField(null=True, blank=True)

    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
    )
    verified_by_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_remarks = models.TextField(null=True, blank=True)

    approved_by_id = models.CharField(db_index=True, max_length=100, null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Complaint Address Change Request"
        verbose_name_plural = "Complaint Address Change Requests"

    def __str__(self):
        return f"AddrChange {self.ticket_id}"

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

    @property
    def verified_by(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User", self.verified_by_id
        )

    @property
    def approved_by(self):
        return self._lookup(
            "app.models.superadmin_masters.auth_user.User", self.approved_by_id
        )

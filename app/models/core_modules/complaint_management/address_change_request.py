from django.conf import settings
from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.models.core_modules.complaint_management.ticket import ComplaintTicket


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

    ticket = models.OneToOneField(
        ComplaintTicket,
        on_delete=models.CASCADE,
        related_name="address_change_request",
    )
    customer = models.ForeignKey(
        CustomerCreation,
        on_delete=models.PROTECT,
        related_name="address_change_requests",
    )

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

    # Requested new flat geo (same FK family as CustomerCreation). Only one
    # of the local-body FKs should be populated at a time.
    new_state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_state_id",
    )
    new_district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_district_id",
    )
    new_area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_area_type_id",
    )
    new_corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_corporation_id",
    )
    new_municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_municipality_id",
    )
    new_town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_town_panchayat_id",
    )
    new_panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_panchayat_union_id",
    )
    new_panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="address_change_requests",
        db_column="new_panchayat_id",
    )

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
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_address_verified",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_remarks = models.TextField(null=True, blank=True)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_address_approved",
    )
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

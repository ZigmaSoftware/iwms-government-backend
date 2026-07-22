from django.db import models
from app.utils.base_models import BaseMaster
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty
from app.models.assets.wastetype import WasteType
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat
from app.utils.comfun import generate_unique_id
from app.utils.customer_qr import (
    QR_SUBPROPERTY_APARTMENT,
    generate_customer_qr_content,
    generate_qr_data as build_customer_qr_data,
    resolve_subproperty_type,
)


def generate_customer_id():
    """Generate readable prefixed ID, e.g., CUS-20251028001"""
    return f"CUS-{generate_unique_id()}"

def generate_apartment_id():
    """Generate readable prefixed ID like APT-20260424001"""
    return f"APT-{generate_unique_id()}"


# Bulk waste generator auto-detection thresholds
BULK_WASTE_SQFT_THRESHOLD = 20000
BULK_WASTE_WATER_LPD_THRESHOLD = 40000
BULK_WASTE_COLLECTION_KG_THRESHOLD = 100


def exceeds_bulk_waste_threshold(sqft, water_consumption_lpd, waste_collection_kg_per_day):
    """True if any of sqft/water-consumption/waste-collection crosses the bulk waste generator threshold."""
    return (
        (sqft is not None and sqft > BULK_WASTE_SQFT_THRESHOLD)
        or (water_consumption_lpd is not None and water_consumption_lpd > BULK_WASTE_WATER_LPD_THRESHOLD)
        or (waste_collection_kg_per_day is not None and waste_collection_kg_per_day > BULK_WASTE_COLLECTION_KG_THRESHOLD)
    )


def get_or_create_apartment_id(apartment_name, latitude, longitude):
        apartment_name = (apartment_name or "").strip().upper()

        existing = CustomerCreation.objects.filter(
            apartment_name__iexact=apartment_name,
            latitude=latitude,
            longitude=longitude,
            is_deleted=False
        ).first()

        if existing and existing.apartment_unique_id:
            return existing.apartment_unique_id

        return generate_apartment_id()

class CustomerCreation(BaseMaster):
    QR_TRIGGER_FIELDS = {
        "customer_name",
        "contact_no",
        "building_no",
        "apartment_name",
        "block_no",
        "flat_no",
        "villa_no",
        "industry_name",
        "industry_type",
        "sub_property",
        "sub_property_id",
    }
    QR_COMPARE_FIELDS = (
        "customer_name",
        "contact_no",
        "building_no",
        "apartment_name",
        "block_no",
        "flat_no",
        "villa_no",
        "industry_name",
        "industry_type",
        "sub_property_id",
    )



    class IDProofType(models.TextChoices):
        AADHAAR = "AADHAAR", "Aadhaar"
        VOTER_ID = "VOTER_ID", "Voter ID"
        PAN_CARD = "PAN_CARD", "PAN Card"
        DRIVING_LICENSE = "DL", "Driving License"
        PASSPORT = "PASSPORT", "Passport"

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_customer_id,
        editable=False,
    )

    customer_name = models.CharField(max_length=100)
    contact_no = models.CharField(max_length=10)
    building_no = models.CharField(max_length=20, null=True, blank=True)
    street = models.CharField(max_length=100, null=True, blank=True)
    area = models.CharField(max_length=50, null=True, blank=True)

    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_creations",
        to_field="unique_id",
        db_column="state_id",
    )
    district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_creations",
        to_field="unique_id",
        db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_creations",
        to_field="unique_id",
        db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_creations",
        to_field="unique_id",
        db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_creations",
        to_field="unique_id",
        db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_creations",
        to_field="unique_id",
        db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_creations",
        to_field="unique_id",
        db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_creations",
        to_field="unique_id",
        db_column="panchayat_id",
    )

    pincode = models.CharField(max_length=10)
    latitude = models.CharField(max_length=100)
    longitude = models.CharField(max_length=100)

    # =============================
    # APARTMENT SUPPORT
    # =============================
    apartment_name = models.CharField(max_length=100, null=True, blank=True)
    block_no = models.CharField(max_length=20, null=True, blank=True)
    flat_no = models.CharField(max_length=20, null=True, blank=True)

    apartment_qr = models.ImageField(
        upload_to="apartment_qr/",
        blank=True,
        null=True
    )

    apartment_unique_id = models.CharField(
    max_length=50,
    null=True,
    blank=True,
    db_index=True
)

    villa_no = models.CharField(max_length=20, null=True, blank=True)
    industry_name = models.CharField(max_length=100, null=True, blank=True)
    industry_type = models.CharField(max_length=100, null=True, blank=True)

    # COMMON QR GROUP ID
    group_qr_id = models.CharField(max_length=100, null=True, blank=True)

    sqft = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    water_consumption_lpd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Water consumption in litres per day",
    )

    waste_collection_kg_per_day = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Waste collection in kg per day",
    )

    id_proof_type = models.CharField(
        max_length=20,
        choices=IDProofType.choices,
        blank=False,
        null=False
    )

    id_no = models.CharField(max_length=100)

    member_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Number of family members in the household",
    )

    family_members = models.JSONField(
        default=list,
        blank=True,
        help_text="List of {member_name, id_proof_type, id_no} dicts for family members",
    )

    property_ref = models.ForeignKey(
        Property,
        on_delete=models.PROTECT,
        related_name="customer_creation",
        db_column="property"
    )

    sub_property = models.ForeignKey(
        SubProperty,
        on_delete=models.PROTECT,
        related_name="customer_creation"
    )

    waste_types = models.ManyToManyField(
        WasteType,
        related_name="customer_creations",
        blank=True,
    )

    # =============================
    # AUTHENTICATION FIELDS
    # =============================

    username = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True,
        help_text="Customer login identifier"
    )

    email = models.EmailField(null=True, blank=True)

    password = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="Django auth password field"
    )

    password_crt_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last password change"
    )

    previous_password = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="Previous hashed password for reuse prevention"
    )

    fcm_token = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Firebase Cloud Messaging device token for the citizen mobile "
                   "app, registered on login. Used to push instant notifications "
                   "(e.g. waste collection status updates) to this customer.",
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    is_staff = models.BooleanField(
        default=False,
        help_text="Django admin-site access flag.",
    )

    is_superuser = models.BooleanField(default=False)
    is_bulkwaste_generator = models.BooleanField(default=False)

    # =============================
    # QR CODE FIELD
    # =============================
    qr_code = models.ImageField(
        upload_to="customer_qr/",
        blank=True,
        null=True
    )

    

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ["customer_name"]

    def __str__(self):
        for local_body, name_attr in (
            (self.corporation, "corporation_name"),
            (self.municipality, "municipality_name"),
            (self.town_panchayat, "town_panchayat_name"),
            (self.panchayat_union, "union_name"),
            (self.panchayat, "panchayat_name"),
        ):
            if local_body:
                location = getattr(local_body, name_attr, "")
                break
        else:
            location = getattr(self.district, "name", "")
        return f"{self.customer_name} ({location})"

    def delete(self, *args, **kwargs):
        """Soft delete this record."""
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])


    def generate_group_qr_id(self):
        """
        Backward-compatible group id:
        apartment customers retain apartment-level grouping,
        other customer types default to their unique customer id.
        """
        sub_property_name = (
            self.sub_property.sub_property_name
            if self.sub_property
            else ""
        )
        if resolve_subproperty_type(sub_property_name) != QR_SUBPROPERTY_APARTMENT:
            return self.unique_id

        apartment_name = (self.apartment_name or "").strip()
        block_no = (self.block_no or "").strip()
        if apartment_name and block_no:
            return f"APT-{apartment_name}-{block_no}"
        return f"APT-{self.unique_id}"

    @property
    def is_authenticated(self):
        return True

    # =============================
    # QR GENERATION LOGIC
    # =============================

    def _should_refresh_qr(self, is_create, update_fields):
        if is_create or not self.qr_code:
            return True

        if update_fields is not None:
            return bool(set(update_fields) & self.QR_TRIGGER_FIELDS)

        previous = (
            CustomerCreation.objects
            .filter(pk=self.pk)
            .values(*self.QR_COMPARE_FIELDS)
            .first()
        )
        if not previous:
            return True

        for field in self.QR_COMPARE_FIELDS:
            if previous.get(field) != getattr(self, field):
                return True

        return False

    def _regenerate_qr_code(self):
        qr_data = build_customer_qr_data(self)
        file_content = generate_customer_qr_content(qr_data)
        file_name = f"{self.unique_id}.png"

        if self.qr_code:
            self.qr_code.delete(save=False)

        self.qr_code.save(file_name, file_content, save=False)
        super().save(update_fields=["qr_code"])

    def save(self, *args, **kwargs):

        if exceeds_bulk_waste_threshold(
            self.sqft, self.water_consumption_lpd, self.waste_collection_kg_per_day
        ):
            self.is_bulkwaste_generator = True

        if self.block_no:
            self.block_no = self.block_no.upper()


        if self.apartment_name and self.latitude and self.longitude:
            if not self.apartment_unique_id:
                self.apartment_unique_id = get_or_create_apartment_id(
                    self.apartment_name,
                    self.latitude,
                    self.longitude
                )

        is_create = self._state.adding
        requested_update_fields = kwargs.get("update_fields")
        qr_refresh_required = self._should_refresh_qr(
            is_create=is_create,
            update_fields=requested_update_fields,
        )

        self.group_qr_id = self.generate_group_qr_id()
        if not self.group_qr_id:
            self.group_qr_id = self.unique_id

        if requested_update_fields is not None:
            merged_update_fields = set(requested_update_fields)
            merged_update_fields.add("group_qr_id")
            kwargs["update_fields"] = list(merged_update_fields)

        super().save(*args, **kwargs)

        if qr_refresh_required:
            self._regenerate_qr_code()

    def generate_qr_data(self):
        return build_customer_qr_data(self)

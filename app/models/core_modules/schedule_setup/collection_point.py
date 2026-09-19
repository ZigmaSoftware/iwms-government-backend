from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id
from django.core.exceptions import ValidationError
from app.models.masters.ward import Ward

def geneate_collection_point_id():
    return f"CP-{generate_unique_id()}"

class Collection_point(BaseMaster):
    CACHE_SCOPES = (
        "collection_point_list",
        "collection_point_detail",
        "trip_plan_list",
        "trip_plan_detail",
    )

    COLLECTION_TYPE_BIN = "bin_collection"
    COLLECTION_TYPE_HOUSEHOLD = "household_collection"
    COLLECTION_TYPE_BULK = "bulk_waste_collection"

    COLLECTION_TYPE_CHOICES = [
        (COLLECTION_TYPE_BIN, "Secondary Collection Point"),
        (COLLECTION_TYPE_HOUSEHOLD, "Household Collection"),
        (COLLECTION_TYPE_BULK, "Bulk Waste Collection"),
    ]

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=geneate_collection_point_id,
        editable=False
    )

    # Government hierarchy — plain CharFields holding the related row's
    # `unique_id` (no DB relation/join), matching the rest of the
    # geo-hierarchy convention.
    country_id = models.CharField(max_length=30, null=True, blank=True)
    state_id = models.CharField(max_length=30, null=True, blank=True)
    district_id = models.CharField(max_length=30, null=True, blank=True)
    area_type_id = models.CharField(max_length=30, null=True, blank=True)
    corporation_id = models.CharField(max_length=30, null=True, blank=True)
    municipality_id = models.CharField(max_length=30, null=True, blank=True)
    town_panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_union_id = models.CharField(max_length=30, null=True, blank=True)
    panchayat_id = models.CharField(max_length=30, null=True, blank=True)
    wards = models.ManyToManyField(
        Ward,
        related_name="collection_points_multi",
        blank=True,
        help_text="Wards this collection point serves.",
    )

    cp_name = models.CharField(max_length=100)
    collection_type = models.CharField(
        max_length=30,
        choices=COLLECTION_TYPE_CHOICES,
        default=COLLECTION_TYPE_BIN,
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    coordinates = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



    def clean(self):
        if not self.district_id:
            raise ValidationError("Collection Point must belong to a district.")
        

    def __str__(self):
        return f"{self.cp_name} ({self.district_id})" if self.district_id else self.cp_name

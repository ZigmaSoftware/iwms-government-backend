from django.db import models

from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_panchayat_union_id():
    return f"PU-{generate_unique_id()}"


class PanchayatUnion(BaseMaster):
    CASCADE_SOFT_DELETE = (
        "wards",
        "bins",
        "vehicles",
        "staff_templates",
        "collection_points",
        "trip_plans",
        "trip_plan_collection_points",
        "daily_trip_logs",
        "daily_trip_collection_points",
        "daily_trip_assignments",
        "daily_trip_household_collections",
        "vehicle_breakdowns",
        "secondary_bin_collection_events",
        "waste_collections",
        "complaint_routing_rules",
        "address_change_requests",
        "complaint_tickets",
        "staff_members",
        "customer_creations",
        "staff_access_configurations",
    )
    CACHE_SCOPES = ("panchayat_union_list", "panchayat_union_detail")

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        default=generate_panchayat_union_id,
        editable=False,
    )
    state_id = models.CharField(max_length=30)
    district_id = models.CharField(max_length=30)
    area_type_id = models.CharField(max_length=30)
    union_name = models.CharField(max_length=100)
    coordinates = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["union_name"]
        unique_together = ("state_id", "district_id", "area_type_id", "union_name")

    def __str__(self):
        return self.union_name

    @property
    def wards(self):
        """Wards under this panchayat union. Ward.panchayat_union_id is a
        plain unique_id string (no DB relation), so this replaces the
        reverse FK accessor `cascade_soft_delete()` (see CASCADE_SOFT_DELETE
        above) and other callers expect; returns a QuerySet, so `.all()`/
        `.filter()`/`.first()` etc. all still work the same as before."""
        from app.models.masters.ward import Ward

        return Ward.objects.filter(panchayat_union_id=self.unique_id)

    @property
    def customer_creations(self):
        """CustomerCreation rows scoped to this panchayat union. See `wards`
        above — CustomerCreation.panchayat_union_id is likewise a plain
        unique_id string now."""
        from app.models.masters.customer_masters.customercreation import CustomerCreation

        return CustomerCreation.objects.filter(panchayat_union_id=self.unique_id)

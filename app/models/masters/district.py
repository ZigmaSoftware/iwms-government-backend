from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id



def generate_district_id():
    return f"DIST-{generate_unique_id()}"

class District(BaseMaster):

    CASCADE_SOFT_DELETE = (
        "area_type",
        "corporations",
        "municipalities",
        "town_panchayats",
        "panchayat_unions",
        "panchayat",
        "wards",
        # consumer tables referencing this district directly
        "leader_logins",
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
        "scoped_staff",
        "staff_members",
        "userscreen_column_permissions",
        "dashboard_widget_permissions",
        "userscreenpermissions",
        "users_district",
        "customer_creations",
        "staff_access_configurations",
    )
    CACHE_SCOPES = ("district_list", "district_detail")

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_district_id
    )

    country_id = models.CharField(max_length=30)

    state_id = models.CharField(max_length=30)

    continent_id = models.CharField(max_length=30)

    name = models.CharField(max_length=100)
    district_code = models.CharField(max_length=20, blank=True, null=True)
    coordinates = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("state_id", "name")   # FIXED

    def __str__(self):
        from app.models.superadmin.common_masters.state import State
        state_name = State.objects.filter(unique_id=self.state_id).values_list("name", flat=True).first()
        return f"{self.name} ({state_name})"

    @property
    def wards(self):
        """Wards directly scoped to this district. Ward.district_id is a
        plain unique_id string (no DB relation), so this replaces the
        reverse FK accessor `cascade_soft_delete()` (see CASCADE_SOFT_DELETE
        above) and other callers expect; returns a QuerySet, so `.all()`/
        `.filter()`/`.first()` etc. all still work the same as before."""
        from app.models.masters.ward import Ward

        return Ward.objects.filter(district_id=self.unique_id)

    @property
    def customer_creations(self):
        """CustomerCreation rows scoped to this district. See `wards` above
        — CustomerCreation.district_id is likewise a plain unique_id string
        now."""
        from app.models.masters.customer_masters.customercreation import CustomerCreation

        return CustomerCreation.objects.filter(district_id=self.unique_id)

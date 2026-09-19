from django.db import models
from app.utils.base_models import BaseMaster
from app.utils.comfun import generate_unique_id


def generate_state_id():
    return f"STATE-{generate_unique_id()}"


class State(BaseMaster):

    CASCADE_SOFT_DELETE = (
        "districts",
        "area_type",
        "corporations",
        "municipalities",
        "town_panchayats",
        "panchayat_unions",
        "panchayat",
        "wards",
        # consumer tables referencing this state directly
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
        "customer_creations",
        "staff_access_configurations",
    )
    CACHE_SCOPES = ("state_list", "state_detail")

    unique_id = models.CharField(
        max_length=30,
        primary_key=True,
        unique=True,
        default=generate_state_id
    )

    country_id = models.CharField(max_length=30)

    continent_id = models.CharField(max_length=30)

    name = models.CharField(max_length=100)
    label = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("country_id", "name")

    def __str__(self):
        from .country import Country
        country_name = Country.objects.filter(unique_id=self.country_id).values_list("name", flat=True).first()
        return f"{self.name} ({country_name})"

    @property
    def wards(self):
        """Wards directly scoped to this state. Ward.state_id is a plain
        unique_id string (no DB relation), so this replaces the reverse FK
        accessor `cascade_soft_delete()` (see CASCADE_SOFT_DELETE above) and
        other callers expect; returns a QuerySet, so `.all()`/`.filter()`/
        `.first()` etc. all still work the same as before."""
        from app.models.masters.ward import Ward

        return Ward.objects.filter(state_id=self.unique_id)

    @property
    def customer_creations(self):
        """CustomerCreation rows scoped to this state. See `wards` above —
        CustomerCreation.state_id is likewise a plain unique_id string now."""
        from app.models.masters.customer_masters.customercreation import CustomerCreation

        return CustomerCreation.objects.filter(state_id=self.unique_id)

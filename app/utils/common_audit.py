from django.db import models
from django.utils import timezone
from app.utils.comfun import generate_unique_id
from app.models.superadmin.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat


def generate_audit_id():
    return f"AUDIT-{generate_unique_id()}"


class CommonAudit(models.Model):

    uuid = models.CharField(
        max_length=50,
        primary_key=True,
        default=generate_audit_id,
        editable=False
    )

    module_name = models.CharField(max_length=150)
    endpoint_name = models.CharField(max_length=150)
    method = models.CharField(max_length=10)

    previous_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)

    object_id = models.CharField(max_length=150, null=True, blank=True)

    createdBy = models.CharField(max_length=150, null=True, blank=True)
    createdAt = models.DateTimeField(default=timezone.now)

    # Flat geo scope block — stamped from the audited instance at write time
    # (see AuditViewSetMixin.log_audit / copy_flat_geo) so staff-facing audit
    # views can be filtered to the requester's own local body hierarchy,
    # mirroring how BinCollectionEvent/DailyTripHouseholdCollection are scoped.
    state = models.ForeignKey(
        State, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="common_audits", to_field="unique_id", db_column="state_id",
    )
    district = models.ForeignKey(
        District, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="common_audits", to_field="unique_id", db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="common_audits", to_field="unique_id", db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="common_audits", to_field="unique_id", db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="common_audits", to_field="unique_id", db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="common_audits", to_field="unique_id", db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="common_audits", to_field="unique_id", db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="common_audits", to_field="unique_id", db_column="panchayat_id",
    )

    class Meta:
        db_table = "common_audit"
        ordering = ["-createdAt"]

    def __str__(self):
        return self.uuid
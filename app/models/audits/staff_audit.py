from django.db import models
from django.utils import timezone

from app.utils.comfun import generate_unique_id
from app.models.common_masters.state import State
from app.models.masters.district import District
from app.models.masters.areatype import AreaType
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.panchayat import Panchayat


def generate_staff_audit_id():
    return f"STAFFAUDIT-{generate_unique_id()}"


class StaffAudit(models.Model):
    """Staff-facing mirror of CommonAudit (app/utils/common_audit.py).

    Every action logged to CommonAudit is also written here (see
    app/utils/audit_mixin.py log_audit/log_common_audit) so the two ledgers
    always stay in sync. CommonAudit remains the super-admin's unscoped,
    system-wide view; this table exists purely so a staff-facing viewset can
    filter rows down to the requester's own local body hierarchy without
    touching CommonAudit's behaviour at all.
    """

    uuid = models.CharField(
        max_length=50,
        primary_key=True,
        default=generate_staff_audit_id,
        editable=False,
    )

    module_name = models.CharField(max_length=150)
    endpoint_name = models.CharField(max_length=150)
    method = models.CharField(max_length=10)

    previous_data = models.JSONField(null=True, blank=True)
    new_data = models.JSONField(null=True, blank=True)

    object_id = models.CharField(max_length=150, null=True, blank=True)

    createdBy = models.CharField(max_length=150, null=True, blank=True)
    createdAt = models.DateTimeField(default=timezone.now)

    # Flat geo scope block, stamped from the audited instance at write time
    # (copy_flat_geo) — the basis for hierarchy-level filtering on the
    # staff-facing audit list.
    state = models.ForeignKey(
        State, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_audits", to_field="unique_id", db_column="state_id",
    )
    district = models.ForeignKey(
        District, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_audits", to_field="unique_id", db_column="district_id",
    )
    area_type = models.ForeignKey(
        AreaType, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_audits", to_field="unique_id", db_column="area_type_id",
    )
    corporation = models.ForeignKey(
        Corporation, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_audits", to_field="unique_id", db_column="corporation_id",
    )
    municipality = models.ForeignKey(
        Municipality, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_audits", to_field="unique_id", db_column="municipality_id",
    )
    town_panchayat = models.ForeignKey(
        TownPanchayat, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_audits", to_field="unique_id", db_column="town_panchayat_id",
    )
    panchayat_union = models.ForeignKey(
        PanchayatUnion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_audits", to_field="unique_id", db_column="panchayat_union_id",
    )
    panchayat = models.ForeignKey(
        Panchayat, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="staff_audits", to_field="unique_id", db_column="panchayat_id",
    )

    class Meta:
        db_table = "staff_audit"
        ordering = ["-createdAt"]

    def __str__(self):
        return self.uuid

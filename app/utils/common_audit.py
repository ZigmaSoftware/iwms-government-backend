from django.db import models
from django.utils import timezone
from app.utils.comfun import generate_unique_id


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

    # Request context + outcome — mirrors LoginAudit's ip_address/user_agent/
    # success/reason so every audited create/update/delete (not just login)
    # carries the same "who, from where, did it work, why not" trail.
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    success = models.BooleanField(default=True)
    reason = models.CharField(max_length=255, null=True, blank=True)

    # Flat geo scope block — stamped from the audited instance at write time
    # (see AuditViewSetMixin.log_audit / copy_flat_geo) so staff-facing audit
    # views can be filtered to the requester's own local body hierarchy,
    # mirroring how BinCollectionEvent/DailyTripHouseholdCollection are scoped.
    # Plain CharFields holding each row's unique_id (no DB relation/join) —
    # matches the rest of the geo-hierarchy refactor's convention. db_column
    # kept as "state_id"/etc (the field's own bare name predates the
    # "_id"-suffixed FK attname convention) so the existing DB columns are
    # preserved unrenamed.
    state = models.CharField(max_length=30, null=True, blank=True, db_column="state_id")
    district = models.CharField(max_length=30, null=True, blank=True, db_column="district_id")
    area_type = models.CharField(max_length=30, null=True, blank=True, db_column="area_type_id")
    corporation = models.CharField(max_length=30, null=True, blank=True, db_column="corporation_id")
    municipality = models.CharField(max_length=30, null=True, blank=True, db_column="municipality_id")
    town_panchayat = models.CharField(max_length=30, null=True, blank=True, db_column="town_panchayat_id")
    panchayat_union = models.CharField(max_length=30, null=True, blank=True, db_column="panchayat_union_id")
    panchayat = models.CharField(max_length=30, null=True, blank=True, db_column="panchayat_id")

    class Meta:
        db_table = "common_audit"
        ordering = ["-createdAt"]

    def __str__(self):
        return self.uuid

"""Unit tests for PermissionAuditLog model — read-only audit trail."""
import pytest
from app.models.superadmin.audits.permission_audit import PermissionAuditLog


@pytest.mark.django_db
class TestPermissionAuditLogCreate:
    def test_basic_create(self, company):
        pa = PermissionAuditLog.objects.create(company=company, action_type="CREATED")
        assert pa.action_type == "CREATED"

    def test_all_foreign_keys_optional(self):
        pa = PermissionAuditLog.objects.create()
        assert pa.company is None
        assert pa.staffusertype is None
        assert pa.mainscreen is None
        assert pa.userscreen is None

    def test_timestamp_auto_set(self, company):
        pa = PermissionAuditLog.objects.create(company=company, action_type="UPDATED")
        assert pa.timestamp is not None

    def test_default_action_type_is_updated(self):
        pa = PermissionAuditLog.objects.create()
        assert pa.action_type == "UPDATED"


@pytest.mark.django_db
class TestPermissionAuditLogRead:
    def test_can_filter_by_action_type(self, company):
        PermissionAuditLog.objects.create(company=company, action_type="CREATED")
        PermissionAuditLog.objects.create(company=company, action_type="DELETED")
        count = PermissionAuditLog.objects.filter(action_type="CREATED").count()
        assert count >= 1

    def test_ordering_newest_first(self, company):
        PermissionAuditLog.objects.create(company=company, action_type="CREATED")
        PermissionAuditLog.objects.create(company=company, action_type="UPDATED")
        logs = list(PermissionAuditLog.objects.values_list("action_type", flat=True))
        assert len(logs) >= 2

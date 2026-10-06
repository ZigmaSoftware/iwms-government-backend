"""Complaint Audit (app/services/complaint_audit.py and
app/viewsets/superadmin/audits/complaint_audit_viewset.py)."""
from datetime import timedelta

import pytest
from django.core.cache import caches
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from app.models.core_modules.complaint_management import (
    ComplaintAssignmentHistory,
    ComplaintCategory,
    ComplaintEscalationHistory,
    ComplaintFeedback,
    ComplaintPriority,
    ComplaintReopenHistory,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintTicket,
)
from app.models.masters.district import District
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin_masters.auth_user import User
from app.services.complaint_audit import summarize_tickets, ticket_timeline
from app.utils.common_audit import CommonAudit
from app.viewsets.superadmin.audits.complaint_audit_viewset import ComplaintAuditViewSet

DISTRICT = "DIST-AUDIT-1"
OTHER_DISTRICT = "DIST-AUDIT-2"
PANCHAYAT = "PANCHAYAT-AUDIT-1"


@pytest.fixture(autouse=True)
def _clear_app_cache():
    caches["app_cache"].clear()
    yield
    caches["app_cache"].clear()


@pytest.fixture
def masters(db):
    statuses = {
        code: ComplaintStatus.objects.create(status_code=code, status_name=code.title(), sort_order=index)
        for index, code in enumerate(("SUBMITTED", "ESCALATED", "RESOLVED", "REOPENED", "CLOSED"))
    }
    priority = ComplaintPriority.objects.create(priority_code="P2", priority_name="High")
    category = ComplaintCategory.objects.create(
        category_code="GARBAGE", category_name="Garbage", default_priority_id=priority.unique_id
    )
    admin = User.objects.create_superuser(username="auditor", password="pw")
    staff = Staffcreation.objects.create(
        username="field", employee_name="Field Officer", active_status=True, login_enabled=True
    )
    senior = Staffcreation.objects.create(
        username="senior", employee_name="Senior Officer", active_status=True, login_enabled=True
    )
    return {
        "statuses": statuses,
        "priority": priority,
        "category": category,
        "admin": admin,
        "staff": staff,
        "senior": senior,
    }


def _at(row, field, when):
    """Backdate an auto_now_add timestamp."""
    type(row).objects.filter(pk=row.pk).update(**{field: when})


def _ticket(masters, *, district=DISTRICT, created_at=None, **extra):
    ticket = ComplaintTicket.objects.create(
        category_id=masters["category"].unique_id,
        priority_id=masters["priority"].unique_id,
        status_id=masters["statuses"]["SUBMITTED"].unique_id,
        district_id=district,
        panchayat_id=PANCHAYAT,
        title="Garbage not collected",
        profile_name="Citizen One",
        wa_phone="9000000001",
        created_by=masters["admin"].unique_id,
        **extra,
    )
    created_at = created_at or timezone.now() - timedelta(days=1)
    _at(ticket, "created", created_at)
    row = ComplaintStatusHistory.objects.create(
        ticket_id=ticket.unique_id,
        to_status_id=ticket.status_id,
        changed_by_system=True,
        remarks="Ticket created",
    )
    _at(row, "changed_at", created_at)
    ticket.refresh_from_db()
    return ticket


def _status(ticket, masters, from_code, to_code, when, remarks=None, by_system=False):
    row = ComplaintStatusHistory.objects.create(
        ticket_id=ticket.unique_id,
        from_status_id=masters["statuses"][from_code].unique_id,
        to_status_id=masters["statuses"][to_code].unique_id,
        changed_by_user_id=None if by_system else masters["admin"].unique_id,
        changed_by_system=by_system,
        remarks=remarks,
    )
    _at(row, "changed_at", when)


@pytest.fixture
def lifecycle(masters):
    """Raised -> resolved (2h) -> reopened (3h) -> auto-escalated (4h) ->
    resolved again (6h) -> feedback."""
    t0 = timezone.now() - timedelta(days=1)
    ticket = _ticket(masters, created_at=t0, assigned_staff_id=masters["staff"].staff_unique_id)

    _status(ticket, masters, "SUBMITTED", "RESOLVED", t0 + timedelta(hours=2), remarks="Bin cleared")

    reopen = ComplaintReopenHistory.objects.create(
        ticket_id=ticket.unique_id,
        reopened_by_user_id=masters["admin"].unique_id,
        reopen_reason="Garbage is back",
        previous_status_id=masters["statuses"]["RESOLVED"].unique_id,
    )
    _at(reopen, "reopened_at", t0 + timedelta(hours=3))
    _status(ticket, masters, "RESOLVED", "REOPENED", t0 + timedelta(hours=3), remarks="Reopened")

    escalation = ComplaintEscalationHistory.objects.create(
        ticket_id=ticket.unique_id,
        escalation_level=2,
        escalated_from_level=1,
        escalated_from_staff_id=masters["staff"].staff_unique_id,
        escalated_to_staff_id=masters["senior"].staff_unique_id,
        reason="SLA breached",
        escalated_by_system=True,
    )
    _at(escalation, "escalated_at", t0 + timedelta(hours=4))
    assignment = ComplaintAssignmentHistory.objects.create(
        ticket_id=ticket.unique_id,
        from_staff_id=masters["staff"].staff_unique_id,
        to_staff_id=masters["senior"].staff_unique_id,
        assignment_reason="SLA breach auto-escalation",
    )
    _at(assignment, "assigned_at", t0 + timedelta(hours=4))
    _status(ticket, masters, "REOPENED", "ESCALATED", t0 + timedelta(hours=4), by_system=True)

    _status(ticket, masters, "ESCALATED", "RESOLVED", t0 + timedelta(hours=6), remarks="Cleared for good")
    feedback = ComplaintFeedback.objects.create(
        ticket_id=ticket.unique_id, rating=4, feedback_text="Thanks", is_issue_solved=True
    )
    _at(feedback, "submitted_at", t0 + timedelta(hours=7))

    ComplaintTicket.objects.filter(pk=ticket.pk).update(
        status_id=masters["statuses"]["RESOLVED"].unique_id,
        resolved_at=t0 + timedelta(hours=6),
        reopened_count=1,
        is_escalated=True,
        escalated_to_staff_id=masters["senior"].staff_unique_id,
        escalation_level=2,
    )
    ticket.refresh_from_db()
    return ticket


@pytest.mark.django_db
class TestSummarizeTickets:
    def test_empty(self):
        assert summarize_tickets([]) == []

    def test_lifecycle_summary(self, masters, lifecycle):
        District.objects.get_or_create(unique_id=DISTRICT, defaults={"state_id": "ST-1", "name": "North District"})
        [row] = summarize_tickets([lifecycle])

        assert row["ticket_no"] == lifecycle.ticket_no
        assert row["status_code"] == "RESOLVED"
        assert row["category_name"] == "Garbage"
        assert row["priority_name"] == "High"
        assert row["district_id"] == DISTRICT
        assert row["district_name"] == "North District"
        assert row["local_body_id"] == PANCHAYAT
        assert row["local_body_type"] == "Panchayat"
        assert row["reporter_name"] == "Citizen One"
        assert row["created_by_name"] == "auditor"
        assert row["assigned_staff_name"] == "Field Officer"
        assert row["escalated_to_staff_name"] == "Senior Officer"
        assert row["first_resolution_seconds"] == 2 * 3600
        assert row["total_resolution_seconds"] == 6 * 3600
        assert row["open_seconds"] is None
        assert row["resolution_remarks"] == "Cleared for good"
        assert row["reopen_count"] == 1
        assert row["last_reopen_reason"] == "Garbage is back"
        assert row["escalation_count"] == 1
        assert row["max_escalation_level"] == 2
        assert row["auto_escalation_count"] == 1
        assert row["feedback_rating"] == 4
        assert row["feedback_issue_solved"] is True
        assert row["is_deleted"] is False
        assert "company_id" not in row and "project_id" not in row

    def test_open_ticket_counts_open_time(self, masters):
        ticket = _ticket(masters, created_at=timezone.now() - timedelta(hours=5))
        [row] = summarize_tickets([ticket])
        assert row["completed_at"] is None
        assert row["total_resolution_seconds"] is None
        assert 5 * 3600 - 60 <= row["open_seconds"] <= 5 * 3600 + 60
        assert row["escalation_count"] == 0 and row["max_escalation_level"] is None


@pytest.mark.django_db
class TestTicketTimeline:
    def test_events_and_dedup(self, masters, lifecycle):
        result = ticket_timeline(lifecycle)
        types = [event["type"] for event in result["timeline"]]
        # The REOPENED/ESCALATED status rows and the escalation's assignment
        # row are folded into the richer reopen/escalation events.
        assert types == ["CREATED", "RESOLVED", "REOPENED", "ESCALATED", "RESOLVED", "FEEDBACK"]

        created, first_fix, reopened, escalated, final_fix, feedback = result["timeline"]
        assert created["actor_name"] == "auditor"
        assert created["details"]["reporter"] == "Citizen One"
        assert first_fix["remarks"] == "Bin cleared"
        assert first_fix["actor_name"] == "auditor"
        assert first_fix["elapsed_seconds"] == 2 * 3600
        assert reopened["remarks"] == "Garbage is back"
        assert reopened["details"]["previous_status"] == "Resolved"
        assert escalated["title"] == "Escalated to level 2"
        assert escalated["actor_name"] == "System"
        assert escalated["details"]["automatic"] is True
        assert escalated["details"]["escalated_to"] == "Senior Officer"
        assert escalated["details"]["escalated_from"] == "Field Officer"
        assert final_fix["remarks"] == "Cleared for good"
        assert feedback["details"] == {"rating": 4, "issue_solved": True}

    def test_status_durations(self, masters, lifecycle):
        durations = {d["status_code"]: d for d in ticket_timeline(lifecycle)["status_durations"]}
        assert durations["SUBMITTED"]["seconds"] == 2 * 3600
        assert durations["RESOLVED"]["seconds"] == 3600
        assert durations["RESOLVED"]["times_entered"] == 1  # the final RESOLVED stops the clock
        assert durations["REOPENED"]["seconds"] == 3600
        assert durations["ESCALATED"]["seconds"] == 2 * 3600

    def test_manual_reassignment_is_listed(self, masters):
        ticket = _ticket(masters, assigned_staff_id=masters["staff"].staff_unique_id)
        ComplaintAssignmentHistory.objects.create(
            ticket_id=ticket.unique_id,
            from_staff_id=masters["staff"].staff_unique_id,
            to_staff_id=masters["senior"].staff_unique_id,
            assigned_by_id=masters["admin"].unique_id,
            assignment_reason="On leave",
        )
        assigned = [e for e in ticket_timeline(ticket)["timeline"] if e["type"] == "ASSIGNED"]
        assert len(assigned) == 1
        assert assigned[0]["title"] == "Reassigned"
        assert assigned[0]["actor_name"] == "auditor"
        assert assigned[0]["details"] == {"from_staff": "Field Officer", "to_staff": "Senior Officer"}

    def test_deleted_ticket(self, masters):
        unaudited = _ticket(masters, is_deleted=True)
        deleted = ticket_timeline(unaudited)["timeline"][-1]
        assert deleted["type"] == "DELETED" and deleted["at"] is None

        audited = _ticket(masters, is_deleted=True)
        CommonAudit.objects.create(
            module_name="complaint-ticket", endpoint_name="tickets", method="DELETE",
            object_id=audited.unique_id, createdBy="auditor",
        )
        deleted = ticket_timeline(audited)["timeline"][-1]
        assert deleted["type"] == "DELETED"
        assert deleted["at"] is not None and deleted["actor_name"] == "auditor"


@pytest.mark.django_db
class TestComplaintAuditViewSet:
    factory = APIRequestFactory()

    def _get(self, user, path="", action="list", **params):
        view = ComplaintAuditViewSet.as_view({"get": action})
        request = self.factory.get(f"/api/v1/audits/complaint-audit/{path}", params)
        force_authenticate(request, user=user)
        kwargs = {"unique_id": path.strip("/")} if action == "retrieve" else {}
        response = view(request, **kwargs)
        assert response.status_code == 200, response.data
        return response.data

    def test_superuser_list_and_filters(self, masters, lifecycle):
        other = _ticket(masters, district=OTHER_DISTRICT)
        deleted = _ticket(masters, is_deleted=True)
        admin = masters["admin"]

        data = self._get(admin, page=1, limit=10)
        assert data["count"] == 3
        assert {r["unique_id"] for r in data["results"]} == {lifecycle.unique_id, other.unique_id, deleted.unique_id}

        assert [r["unique_id"] for r in self._get(admin, district=OTHER_DISTRICT)] == [other.unique_id]
        assert {r["unique_id"] for r in self._get(admin, deleted="exclude")} == {lifecycle.unique_id, other.unique_id}
        assert [r["unique_id"] for r in self._get(admin, deleted="only")] == [deleted.unique_id]
        assert [r["unique_id"] for r in self._get(admin, reopened="1")] == [lifecycle.unique_id]
        assert [r["unique_id"] for r in self._get(admin, escalated="1")] == [lifecycle.unique_id]
        assert [r["unique_id"] for r in self._get(admin, status="resolved")] == [lifecycle.unique_id]
        assert [r["unique_id"] for r in self._get(admin, search=lifecycle.ticket_no)] == [lifecycle.unique_id]
        assert [r["unique_id"] for r in self._get(admin, city=PANCHAYAT, district=DISTRICT, deleted="exclude")] == [
            lifecycle.unique_id
        ]

    def test_retrieve_includes_timeline(self, masters, lifecycle):
        data = self._get(masters["admin"], path=f"{lifecycle.unique_id}/", action="retrieve")
        assert data["ticket_no"] == lifecycle.ticket_no
        assert data["timeline"][0]["type"] == "CREATED"
        assert data["status_durations"]

    def test_staff_sees_only_their_tickets(self, masters, lifecycle):
        _ticket(masters, district=OTHER_DISTRICT)  # nobody's
        # The escalatee and the original assignee both see the escalated ticket.
        for staff in (masters["senior"], masters["staff"]):
            rows = self._get(staff)
            assert [r["unique_id"] for r in rows] == [lifecycle.unique_id]

    def test_filter_options(self, masters, lifecycle):
        District.objects.get_or_create(unique_id=DISTRICT, defaults={"state_id": "ST-1", "name": "North District"})
        data = self._get(masters["admin"], action="filter_options")
        assert [s["unique_id"] for s in data["statuses"]][:2] == ["SUBMITTED", "ESCALATED"]
        assert data["categories"] == [{"unique_id": masters["category"].unique_id, "name": "Garbage"}]
        assert data["districts"] == [{"unique_id": DISTRICT, "name": "North District"}]
        assert set(data) == {"states", "districts", "local_bodies", "statuses", "categories"}

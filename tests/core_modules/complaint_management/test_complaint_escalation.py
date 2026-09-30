"""Staff-Hierarchy-driven complaint assignment and auto-escalation
(app/services/complaint_escalation.py)."""
from datetime import timedelta

import pytest
from django.core.cache import caches
from django.utils import timezone

from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.escalation_history import ComplaintEscalationHistory
from app.models.core_modules.complaint_management.notification import ComplaintNotification
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.models.core_modules.complaint_management.sla_escalation_level import ComplaintSlaEscalationLevel
from app.models.core_modules.complaint_management.sla_rule_master import ComplaintSlaRule
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.staffHierarchy import StaffHierarchy
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.core_modules.complaint_management.master_serializers import ComplaintSlaRuleSerializer
from app.services.complaint_escalation import (
    check_and_escalate_overdue_tickets,
    escalate_ticket,
    hierarchy_level_options,
    restart_escalation_clock,
    role_levels,
    ticket_geo,
)
from app.utils.complaint_ticket_routing import apply_routing_and_sla

DISTRICT = "DIST-TEST-1"
PANCHAYAT = "PANCHAYAT-TEST-1"
OTHER_PANCHAYAT = "PANCHAYAT-TEST-2"


@pytest.fixture(autouse=True)
def _clear_app_cache():
    caches["app_cache"].clear()
    yield
    caches["app_cache"].clear()


@pytest.fixture
def setup(db):
    usertype = UserType.objects.create(name="government")

    def role(name, level):
        return GovernmentStaffUserType.objects.create(name=name, level=level, usertype_id=usertype.unique_id)

    roles = {
        "operator": role("govt_panchayat_operator", "panchayat"),
        "supervisor": role("govt_panchayat_supervisor", "panchayat"),
        "officer": role("govt_district_officer", "district"),
        "admin": role("govt_district_admin", "district"),
    }
    # operator(1) -> supervisor(2) -> officer(3) -> admin (no row of its own)
    for child, head, level in (
        ("operator", "supervisor", 1),
        ("supervisor", "officer", 2),
        ("officer", "admin", 3),
    ):
        StaffHierarchy.objects.create(
            governmentusertype_id=roles[child].unique_id,
            reports_to_governmentusertype_id=roles[head].unique_id,
            hierarchy_level=level,
        )

    def staff(name, role_key, **geo):
        return Staffcreation.objects.create(
            username=name,
            employee_name=name,
            governmentusertype_id=roles[role_key].unique_id,
            active_status=True,
            login_enabled=True,
            **geo,
        )

    people = {
        "operator": staff("operator", "operator", district_id=DISTRICT, panchayat_id=PANCHAYAT),
        "supervisor": staff("supervisor", "supervisor", district_id=DISTRICT, panchayat_id=PANCHAYAT),
        "other_supervisor": staff("other-supervisor", "supervisor", district_id=DISTRICT, panchayat_id=OTHER_PANCHAYAT),
        "officer": staff("officer", "officer", district_id=DISTRICT),
        "admin": staff("admin", "admin", district_id=DISTRICT),
    }

    for code, final, reopen in (
        ("SUBMITTED", False, False),
        ("ESCALATED", False, False),
        ("RESOLVED", False, True),
        ("REOPENED", False, False),
        ("CLOSED", True, False),
    ):
        ComplaintStatus.objects.create(status_code=code, status_name=code.title(), is_final=final, allow_reopen=reopen)

    priority = ComplaintPriority.objects.create(priority_code="P2", priority_name="High")
    category = ComplaintCategory.objects.create(
        category_code="GARBAGE", category_name="Garbage", default_priority_id=priority.unique_id
    )
    rule = ComplaintSlaRule.objects.create(
        category_id=category.unique_id, priority_id=priority.unique_id
    )
    # Level 1 (operator) disabled: tickets start at the supervisor.
    for level, enabled, minutes in ((1, False, 30), (2, True, 60), (3, True, 120), (4, True, 240)):
        ComplaintSlaEscalationLevel.objects.create(
            sla_rule_id=rule.unique_id, level=level, is_enabled=enabled, resolve_within_minutes=minutes
        )
    return {"roles": roles, "people": people, "category": category, "priority": priority, "rule": rule}


def _ticket(setup, panchayat=PANCHAYAT):
    ticket = ComplaintTicket.objects.create(
        category_id=setup["category"].unique_id,
        priority_id=setup["priority"].unique_id,
        status_id=ComplaintStatus.objects.get(status_code="SUBMITTED").unique_id,
        district_id=DISTRICT,
        panchayat_id=panchayat,
        title="Garbage not collected",
    )
    apply_routing_and_sla(ticket, save=True)
    ticket.refresh_from_db()
    return ticket


def _make_overdue(ticket):
    ComplaintTicket.objects.filter(pk=ticket.pk).update(next_escalation_due_at=timezone.now() - timedelta(minutes=1))


@pytest.mark.django_db
class TestHierarchyLevels:
    def test_head_without_own_row_sits_one_level_above(self, setup):
        levels = role_levels(ticket_geo(_ticket(setup)))
        roles = setup["roles"]
        assert levels[roles["operator"].unique_id] == 1
        assert levels[roles["supervisor"].unique_id] == 2
        assert levels[roles["officer"].unique_id] == 3
        assert levels[roles["admin"].unique_id] == 4

    def test_level_options_list_roles_per_level(self, setup):
        options = {o["level"]: [r["name"] for r in o["roles"]] for o in hierarchy_level_options()}
        assert options == {
            1: ["govt_panchayat_operator"],
            2: ["govt_panchayat_supervisor"],
            3: ["govt_district_officer"],
            4: ["govt_district_admin"],
        }


@pytest.mark.django_db
class TestEntryAssignment:
    def test_new_ticket_goes_to_lowest_enabled_level_in_its_area(self, setup):
        ticket = _ticket(setup)
        assert ticket.assigned_staff_id == setup["people"]["supervisor"].staff_unique_id
        assert ticket.escalation_level == 2
        remaining = ticket.next_escalation_due_at - timezone.now()
        assert timedelta(minutes=59) < remaining <= timedelta(minutes=60)
        assert ComplaintNotification.objects.filter(
            ticket_id=ticket.unique_id,
            event_type="ASSIGNED",
            recipient_staff_id=setup["people"]["supervisor"].staff_unique_id,
        ).exists()

    def test_other_panchayat_gets_its_own_supervisor(self, setup):
        ticket = _ticket(setup, panchayat=OTHER_PANCHAYAT)
        assert ticket.assigned_staff_id == setup["people"]["other_supervisor"].staff_unique_id

    def test_rule_without_escalation_levels_leaves_ticket_unassigned(self, setup):
        ComplaintSlaEscalationLevel.objects.all().delete()
        ticket = _ticket(setup)
        assert ticket.assigned_staff_id is None
        assert ticket.next_escalation_due_at is None


@pytest.mark.django_db
class TestAutoEscalation:
    def test_overdue_ticket_climbs_the_chain_then_stops(self, setup):
        people = setup["people"]
        ticket = _ticket(setup)

        _make_overdue(ticket)
        assert check_and_escalate_overdue_tickets() == 1
        ticket.refresh_from_db()
        assert ticket.escalation_level == 3
        assert ticket.escalated_to_staff_id == people["officer"].staff_unique_id
        assert ticket.assigned_staff_id == people["supervisor"].staff_unique_id
        assert ticket.is_escalated
        assert ticket.status.status_code == "ESCALATED"

        _make_overdue(ticket)
        assert check_and_escalate_overdue_tickets() == 1
        ticket.refresh_from_db()
        assert ticket.escalation_level == 4
        assert ticket.escalated_to_staff_id == people["admin"].staff_unique_id

        # Top of the chain: nothing to escalate to, deadline cleared.
        _make_overdue(ticket)
        assert check_and_escalate_overdue_tickets() == 0
        ticket.refresh_from_db()
        assert ticket.next_escalation_due_at is None
        assert ticket.escalated_to_staff_id == people["admin"].staff_unique_id

        history = ComplaintEscalationHistory.objects.filter(ticket_id=ticket.unique_id).order_by("escalation_level")
        assert [(h.escalated_from_level, h.escalation_level) for h in history] == [(2, 3), (3, 4)]
        assert history[0].escalated_from_staff_id == people["supervisor"].staff_unique_id
        assert all(h.escalated_by_system for h in history)
        assert ComplaintNotification.objects.filter(
            ticket_id=ticket.unique_id, event_type="ESCALATED_TO", recipient_staff_id=people["officer"].staff_unique_id
        ).exists()

    def test_ticket_not_yet_due_is_left_alone(self, setup):
        ticket = _ticket(setup)
        assert check_and_escalate_overdue_tickets() == 0
        ticket.refresh_from_db()
        assert ticket.escalation_level == 2

    def test_resolved_ticket_is_never_escalated(self, setup):
        ticket = _ticket(setup)
        ticket.status_id = ComplaintStatus.objects.get(status_code="RESOLVED").unique_id
        ticket.save(update_fields=["status_id"])
        _make_overdue(ticket)
        assert check_and_escalate_overdue_tickets() == 0

    def test_disabled_level_is_skipped_as_hop_target(self, setup):
        ComplaintSlaEscalationLevel.objects.filter(level=3).update(is_enabled=False)
        ticket = _ticket(setup)
        _make_overdue(ticket)
        check_and_escalate_overdue_tickets()
        ticket.refresh_from_db()
        assert ticket.escalation_level == 4
        assert ticket.escalated_to_staff_id == setup["people"]["admin"].staff_unique_id

    def test_manual_escalation_records_the_actor(self, setup):
        ticket = escalate_ticket(_ticket(setup), reason="Citizen called twice", by_system=False)
        assert ticket.escalation_level == 3
        entry = ComplaintEscalationHistory.objects.get(ticket_id=ticket.unique_id)
        assert not entry.escalated_by_system
        assert entry.reason == "Citizen called twice"

    def test_reopen_restarts_current_level_window(self, setup):
        ticket = _ticket(setup)
        ComplaintTicket.objects.filter(pk=ticket.pk).update(next_escalation_due_at=None)
        ticket.refresh_from_db()
        restart_escalation_clock(ticket)
        ticket.refresh_from_db()
        assert ticket.next_escalation_due_at > timezone.now() + timedelta(minutes=59)


@pytest.mark.django_db
class TestSlaRuleSerializer:
    def test_escalation_levels_replace_existing_rows(self, setup):
        rule = setup["rule"]
        serializer = ComplaintSlaRuleSerializer(
            instance=rule,
            data={"escalation_levels": [{"level": 2, "is_enabled": True, "resolve_within_minutes": 90}]},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        assert list(rule.escalation_levels.values_list("level", "resolve_within_minutes")) == [(2, 90)]
        assert serializer.data["escalation_levels"][0]["resolve_within_minutes"] == 90

    def test_duplicate_levels_rejected(self, setup):
        serializer = ComplaintSlaRuleSerializer(
            instance=setup["rule"],
            data={"escalation_levels": [
                {"level": 2, "resolve_within_minutes": 60},
                {"level": 2, "resolve_within_minutes": 90},
            ]},
            partial=True,
        )
        assert not serializer.is_valid()
        assert "escalation_levels" in serializer.errors


@pytest.fixture
def api_client(db):
    import jwt
    from django.conf import settings
    from rest_framework.test import APIClient

    from app.models.superadmin_masters.auth_user import User

    user = User.objects.create_user(username="complaint-tester", is_superuser=True)
    token = jwt.encode({"unique_id": user.unique_id}, settings.SECRET_KEY, algorithm="HS256")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.mark.django_db
class TestTicketApi:
    BASE = "/api/v1/complaint-ticket/tickets/"

    def test_removed_sla_fields_are_gone(self, setup, api_client):
        ticket = _ticket(setup)
        body = api_client.get(f"{self.BASE}{ticket.unique_id}/").json()
        for field in ("sla_due_at", "first_response_due_at", "sla_breached", "sla_time_remaining_seconds"):
            assert field not in body
        rule = ComplaintSlaRuleSerializer(setup["rule"]).data
        assert "assign_within_minutes" not in rule and "resolve_within_minutes" not in rule

    def test_detail_exposes_escalation_state(self, setup, api_client):
        ticket = _ticket(setup)
        response = api_client.get(f"{self.BASE}{ticket.unique_id}/")
        assert response.status_code == 200, response.content
        body = response.json()
        assert body["assigned_staff_name"] == "supervisor"
        assert body["escalation_level"] == 2
        assert body["escalation_level_name"] == "govt_panchayat_supervisor"
        assert 0 < body["escalation_time_remaining_seconds"] <= 3600
        assert "assigned_team_id" not in body

    def test_escalate_action_hops_one_level(self, setup, api_client):
        ticket = _ticket(setup)
        response = api_client.post(f"{self.BASE}{ticket.unique_id}/escalate/", {"reason": "urgent"}, format="json")
        assert response.status_code == 200, response.content
        assert response.json()["escalated_to_staff_name"] == "officer"

    def test_resolve_stops_the_clock(self, setup, api_client):
        ticket = _ticket(setup)
        response = api_client.post(f"{self.BASE}{ticket.unique_id}/resolve/", {}, format="json")
        assert response.status_code == 200, response.content
        ticket.refresh_from_db()
        assert ticket.next_escalation_due_at is None

    def test_hierarchy_levels_endpoint(self, setup, api_client):
        response = api_client.get("/api/v1/complaint-ticket/sla-rules/hierarchy-levels/")
        assert response.status_code == 200, response.content
        assert [row["level"] for row in response.json()] == [1, 2, 3, 4]

    def test_teams_endpoint_is_gone(self, setup, api_client):
        assert api_client.get("/api/v1/complaint-ticket/teams/").status_code == 404


@pytest.fixture
def places(db):
    """Erode district with Anthiyur panchayat; Chennai district with Chennai
    corporation — real masters, since SLA rule scopes are validated."""
    from app.models.masters.corporation import Corporation
    from app.models.masters.district import District
    from app.models.masters.panchayat import Panchayat

    erode = District.objects.create(name="Erode", state_id="STATE-TN", country_id="COUNTRY-IN", continent_id="CONT-AS")
    chennai = District.objects.create(name="Chennai", state_id="STATE-TN", country_id="COUNTRY-IN", continent_id="CONT-AS")
    anthiyur = Panchayat.objects.create(panchayat_name="Anthiyur", state_id="STATE-TN", district_id=erode.unique_id)
    chennai_corp = Corporation.objects.create(
        corporation_name="Chennai Corporation", state_id="STATE-TN", district_id=chennai.unique_id, area_type_id="AREA-URBAN"
    )
    return {"erode": erode, "chennai": chennai, "anthiyur": anthiyur, "chennai_corp": chennai_corp}


def _scoped_rule(setup, levels, **scope):
    serializer = ComplaintSlaRuleSerializer(data={
        "category_id": setup["category"].unique_id,
        "priority_id": setup["priority"].unique_id,
        "escalation_levels": [
            {"level": level, "is_enabled": True, "resolve_within_minutes": minutes} for level, minutes in levels
        ],
        **scope,
    })
    assert serializer.is_valid(), serializer.errors
    return serializer.save()


def _ticket_at(setup, **geo):
    ticket = ComplaintTicket.objects.create(
        category_id=setup["category"].unique_id,
        priority_id=setup["priority"].unique_id,
        status_id=ComplaintStatus.objects.get(status_code="SUBMITTED").unique_id,
        title="Garbage not collected",
        **geo,
    )
    apply_routing_and_sla(ticket, save=True)
    ticket.refresh_from_db()
    return ticket


def _window_minutes(ticket):
    return round((ticket.next_escalation_due_at - timezone.now()).total_seconds() / 60)


@pytest.mark.django_db
class TestAreaSpecificEscalation:
    def test_each_area_escalates_on_its_own_rule(self, setup, places):
        people = setup["people"]
        erode, chennai = places["erode"].unique_id, places["chennai"].unique_id
        anthiyur, chennai_corp = places["anthiyur"].unique_id, places["chennai_corp"].unique_id
        for key, district, panchayat in (("supervisor", erode, anthiyur), ("officer", erode, None), ("admin", erode, None)):
            Staffcreation.objects.filter(pk=people[key].pk).update(district_id=district, panchayat_id=panchayat)
        # Chennai Corporation staff for the same roles.
        chennai_officer = Staffcreation.objects.create(
            username="chennai-officer", employee_name="chennai-officer", active_status=True, login_enabled=True,
            governmentusertype_id=setup["roles"]["officer"].unique_id, district_id=chennai,
        )
        chennai_admin = Staffcreation.objects.create(
            username="chennai-admin", employee_name="chennai-admin", active_status=True, login_enabled=True,
            governmentusertype_id=setup["roles"]["admin"].unique_id, district_id=chennai,
        )

        # Anthiyur: supervisor has 15 minutes, then the officer 30.
        _scoped_rule(setup, [(2, 15), (3, 30)], panchayat_id=anthiyur)
        # Chennai Corporation: skip the supervisor, officer first (45m), then admin (90m).
        _scoped_rule(setup, [(3, 45), (4, 90)], corporation_id=chennai_corp)

        anthiyur_ticket = _ticket_at(setup, district_id=erode, panchayat_id=anthiyur)
        assert anthiyur_ticket.assigned_staff_id == people["supervisor"].staff_unique_id
        assert anthiyur_ticket.escalation_level == 2
        assert _window_minutes(anthiyur_ticket) == 15

        chennai_ticket = _ticket_at(setup, district_id=chennai, corporation_id=chennai_corp)
        assert chennai_ticket.assigned_staff_id == chennai_officer.staff_unique_id
        assert chennai_ticket.escalation_level == 3
        assert _window_minutes(chennai_ticket) == 45

        # Anywhere else in Erode falls back to the unscoped rule. That
        # panchayat has no supervisor, so it starts at the officer (L3, 120m).
        elsewhere = _ticket_at(setup, district_id=erode, panchayat_id=PANCHAYAT)
        assert elsewhere.escalation_level == 3
        assert elsewhere.assigned_staff_id == people["officer"].staff_unique_id
        assert _window_minutes(elsewhere) == 120

        # And each keeps climbing on its own rule's windows.
        _make_overdue(chennai_ticket)
        _make_overdue(anthiyur_ticket)
        check_and_escalate_overdue_tickets()
        chennai_ticket.refresh_from_db()
        anthiyur_ticket.refresh_from_db()
        assert chennai_ticket.escalated_to_staff_id == chennai_admin.staff_unique_id
        assert _window_minutes(chennai_ticket) == 90
        assert anthiyur_ticket.escalated_to_staff_id == people["officer"].staff_unique_id
        assert _window_minutes(anthiyur_ticket) == 30

    def test_scope_is_stored_with_parents_and_labelled(self, setup, places):
        rule = _scoped_rule(setup, [(2, 15)], panchayat_id=places["anthiyur"].unique_id)
        assert rule.district_id == places["erode"].unique_id
        assert rule.state_id == "STATE-TN"
        data = ComplaintSlaRuleSerializer(rule).data
        assert data["scope_level"] == "Panchayat"
        assert data["scope_label"].endswith("Anthiyur")

    def test_duplicate_rule_for_same_place_rejected(self, setup, places):
        _scoped_rule(setup, [(2, 15)], panchayat_id=places["anthiyur"].unique_id)
        serializer = ComplaintSlaRuleSerializer(data={
            "category_id": setup["category"].unique_id,
            "priority_id": setup["priority"].unique_id,
            "panchayat_id": places["anthiyur"].unique_id,
        })
        assert not serializer.is_valid()

    def test_hierarchy_levels_follow_the_area(self, setup, places, api_client):
        # A Chennai-only chain: officer (1) -> admin.
        StaffHierarchy.objects.create(
            governmentusertype_id=setup["roles"]["officer"].unique_id,
            reports_to_governmentusertype_id=setup["roles"]["admin"].unique_id,
            hierarchy_level=1,
            district_id=places["chennai"].unique_id,
        )
        response = api_client.get(
            "/api/v1/complaint-ticket/sla-rules/hierarchy-levels/",
            {"corporation_id": places["chennai_corp"].unique_id},
        )
        assert response.status_code == 200, response.content
        levels = {row["level"]: [role["name"] for role in row["roles"]] for row in response.json()}
        # The Chennai-scoped officer row (L1) overrides the unscoped one (L3);
        # panchayat roles are left out for a corporation.
        assert levels == {1: ["govt_district_officer"], 2: ["govt_district_admin"]}


@pytest.mark.django_db
class TestBareRelationKeys:
    """The admin forms send `category`/`priority`/`district` (pre-0026 names)."""

    def test_sla_rule_accepts_and_returns_bare_keys(self, setup, places):
        # Through the serializer, not POST: the test DB has no staff_audit
        # table for AuditViewSetMixin (see test_staff_hierarchy_api.py).
        serializer = ComplaintSlaRuleSerializer(data={
            "category": setup["category"].unique_id,
            "priority": setup["priority"].unique_id,
            "district_id": places["chennai"].unique_id,
        })
        assert serializer.is_valid(), serializer.errors
        rule = serializer.save()
        data = ComplaintSlaRuleSerializer(rule).data
        assert data["category"] == data["category_id"] == setup["category"].unique_id
        assert data["district"] == places["chennai"].unique_id

    def test_ticket_accepts_bare_keys(self, setup):
        from app.serializers.core_modules.complaint_management.transaction_serializers import ComplaintTicketSerializer

        serializer = ComplaintTicketSerializer(data={
            "category": setup["category"].unique_id,
            "priority": setup["priority"].unique_id,
            "status": ComplaintStatus.objects.get(status_code="SUBMITTED").unique_id,
            "district": DISTRICT,
            "panchayat": PANCHAYAT,
            "title": "Garbage",
        })
        assert serializer.is_valid(), serializer.errors
        ticket = serializer.save()
        assert (ticket.district_id, ticket.panchayat_id) == (DISTRICT, PANCHAYAT)


def _as_staff(staff, action, method="get", unique_id=None, data=None, params=None):
    """Call ComplaintTicketViewSet directly as `staff` (skips the screen-
    permission middleware, which needs UserScreenPermission rows)."""
    from rest_framework.test import APIRequestFactory, force_authenticate

    from app.viewsets.core_modules.complaint_management.ticket_viewset import ComplaintTicketViewSet

    factory = APIRequestFactory()
    path = "/api/v1/complaint-ticket/tickets/"
    request = factory.post(path, data or {}, format="json") if method == "post" else factory.get(path, params or {})
    force_authenticate(request, user=staff)
    view = ComplaintTicketViewSet.as_view({method: action})
    return view(request, unique_id=unique_id) if unique_id else view(request)


def _rows(response):
    body = response.data
    return body.get("results", body) if isinstance(body, dict) else body


@pytest.mark.django_db
class TestEscalatedTicketIsViewOnlyForLowerLevel:
    def _escalated(self, setup):
        ticket = _ticket(setup)
        _make_overdue(ticket)
        check_and_escalate_overdue_tickets()  # supervisor (L2) -> officer (L3)
        return ticket

    def test_supervisor_still_sees_it_in_my_tasks_as_view_only(self, setup):
        ticket = self._escalated(setup)
        mine = _as_staff(setup["people"]["supervisor"], "list", params={"mine": 1})
        assert mine.status_code == 200, mine.data
        row = next(r for r in _rows(mine) if r["unique_id"] == ticket.unique_id)
        assert row["is_escalated"] and row["escalated_to_staff_name"] == "officer"
        assert row["can_act"] is False

        officer_row = next(
            r for r in _rows(_as_staff(setup["people"]["officer"], "list", params={"mine": 1}))
            if r["unique_id"] == ticket.unique_id
        )
        assert officer_row["can_act"] is True

    @pytest.mark.parametrize("action, data", [
        ("resolve", {"resolution_note": "done"}),
        ("change_status", {"status_code": "RESOLVED"}),
        ("escalate", {"reason": "again"}),
        ("assign", {"staff": "anyone"}),
    ])
    def test_supervisor_cannot_act_on_it(self, setup, action, data):
        ticket = self._escalated(setup)
        response = _as_staff(setup["people"]["supervisor"], action, method="post", unique_id=ticket.unique_id, data=data)
        assert response.status_code == 403, response.data
        ticket.refresh_from_db()
        assert ticket.status.status_code == "ESCALATED"
        assert ticket.escalation_level == 3

    def test_supervisor_can_still_comment(self, setup):
        ticket = self._escalated(setup)
        response = _as_staff(setup["people"]["supervisor"], "add_comment", method="post", unique_id=ticket.unique_id,
                             data={"comment_text": "Context for the officer"})
        assert response.status_code == 201, response.data

    def test_officer_it_was_escalated_to_can_resolve(self, setup):
        ticket = self._escalated(setup)
        response = _as_staff(setup["people"]["officer"], "resolve", method="post", unique_id=ticket.unique_id,
                             data={"resolution_note": "Cleared"})
        assert response.status_code == 200, response.data
        ticket.refresh_from_db()
        assert ticket.status.status_code == "RESOLVED"
        assert ticket.next_escalation_due_at is None

    def test_before_escalation_supervisor_can_resolve(self, setup):
        ticket = _ticket(setup)
        response = _as_staff(setup["people"]["supervisor"], "resolve", method="post", unique_id=ticket.unique_id, data={})
        assert response.status_code == 200, response.data

    def test_unrelated_staff_do_not_get_it_in_my_tasks(self, setup):
        ticket = _ticket(setup)
        rows = _rows(_as_staff(setup["people"]["other_supervisor"], "list", params={"mine": 1}))
        assert ticket.unique_id not in {r["unique_id"] for r in rows}


@pytest.mark.django_db
def test_my_tasks_location_filters_narrow_the_list(setup):
    supervisor = setup["people"]["supervisor"]
    here = _ticket(setup)
    elsewhere = _ticket(setup)
    ComplaintTicket.objects.filter(pk=elsewhere.pk).update(district_id="DIST-OTHER")

    def ids(**params):
        return {r["unique_id"] for r in _rows(_as_staff(supervisor, "list", params={"mine": 1, **params}))}

    assert {here.unique_id, elsewhere.unique_id} <= ids()
    assert ids(district=DISTRICT) >= {here.unique_id} and elsewhere.unique_id not in ids(district=DISTRICT)
    assert ids(city=PANCHAYAT) >= {here.unique_id}
    assert ids(city="PANCHAYAT-NONE") == set()


@pytest.mark.django_db
def test_super_admin_my_tasks_lists_every_ticket(setup):
    from app.models.superadmin_masters.auth_user import User

    admin = User.objects.create_user(username="platform-admin", is_superuser=True)
    first = _ticket(setup)
    second = _ticket(setup, panchayat=OTHER_PANCHAYAT)
    rows = _rows(_as_staff(admin, "list", params={"mine": 1}))
    assert {first.unique_id, second.unique_id} <= {r["unique_id"] for r in rows}
    # Location filters still apply on top.
    rows = _rows(_as_staff(admin, "list", params={"mine": 1, "city": OTHER_PANCHAYAT}))
    assert {r["unique_id"] for r in rows} == {second.unique_id}


@pytest.mark.django_db
def test_area_type_filter_matches_tickets_saved_with_only_a_local_body(setup, places):
    from app.models.superadmin_masters.auth_user import User

    anthiyur = places["anthiyur"]
    anthiyur.area_type_id = "AREA-RURAL"
    anthiyur.save(update_fields=["area_type_id"])
    ticket = _ticket_at(setup, district_id=places["erode"].unique_id, panchayat_id=anthiyur.unique_id)
    # Older rows have no area type stored at all.
    ComplaintTicket.objects.filter(pk=ticket.pk).update(area_type_id=None)

    admin = User.objects.create_user(username="platform-admin", is_superuser=True)
    params = {
        "mine": 1, "state": "STATE-TN", "district": places["erode"].unique_id,
        "area_type": "AREA-RURAL", "city": anthiyur.unique_id,
    }
    assert {r["unique_id"] for r in _rows(_as_staff(admin, "list", params=params))} == {ticket.unique_id}
    assert _rows(_as_staff(admin, "list", params={**params, "area_type": "AREA-URBAN", "city": ""})) == []


@pytest.mark.django_db
def test_new_ticket_stores_area_type_from_its_local_body(setup, places):
    anthiyur = places["anthiyur"]
    anthiyur.area_type_id = "AREA-RURAL"
    anthiyur.save(update_fields=["area_type_id"])
    ticket = _ticket_at(setup, panchayat_id=anthiyur.unique_id)
    assert (ticket.state_id, ticket.district_id, ticket.area_type_id) == (
        "STATE-TN", places["erode"].unique_id, "AREA-RURAL",
    )


@pytest.mark.django_db
def test_panchayat_union_ticket_follows_the_union_chain(setup):
    """A union ticket goes to the union's own chain, not the panchayat's —
    even when a union officer's record also names a panchayat."""
    usertype = UserType.objects.first()

    def role(name):
        return GovernmentStaffUserType.objects.create(name=name, level="panchayat_union", usertype_id=usertype.unique_id)

    union_supervisor, union_inspector, union_admin = (
        role("govt_panchayat_union_supervisor"), role("govt_panchayat_union_inspector"), role("govt_panchayat_union_admin")
    )
    UNION = "PU-TEST-1"
    for child, head, level in ((union_supervisor, union_inspector, 3), (union_inspector, union_admin, 4)):
        StaffHierarchy.objects.create(
            governmentusertype_id=child.unique_id, reports_to_governmentusertype_id=head.unique_id,
            hierarchy_level=level, district_id=DISTRICT, panchayat_union_id=UNION,
        )

    def union_staff(name, role_obj):
        # Stray panchayat alongside the union, as seen in real records.
        return Staffcreation.objects.create(
            username=name, employee_name=name, governmentusertype_id=role_obj.unique_id, active_status=True,
            login_enabled=True, district_id=DISTRICT, panchayat_union_id=UNION, panchayat_id=PANCHAYAT,
        )

    sup, insp, adm = union_staff("u-sup", union_supervisor), union_staff("u-insp", union_inspector), union_staff("u-adm", union_admin)
    # The union admin heads the chain one above the inspector (L5).
    ComplaintSlaEscalationLevel.objects.create(
        sla_rule_id=setup["rule"].unique_id, level=5, is_enabled=True, resolve_within_minutes=480
    )

    ticket = _ticket_at(setup, district_id=DISTRICT, panchayat_union_id=UNION)
    assert ticket.assigned_staff_id == sup.staff_unique_id
    assert ticket.escalation_level == 3

    _make_overdue(ticket)
    check_and_escalate_overdue_tickets()
    ticket.refresh_from_db()
    assert ticket.escalated_to_staff_id == insp.staff_unique_id

    _make_overdue(ticket)
    check_and_escalate_overdue_tickets()
    ticket.refresh_from_db()
    assert ticket.escalated_to_staff_id == adm.staff_unique_id

    # The panchayat's own supervisor never receives union tickets.
    assert setup["people"]["supervisor"].staff_unique_id not in (ticket.assigned_staff_id, ticket.escalated_to_staff_id)


@pytest.mark.django_db
class TestRuleEditReschedulesOpenTickets:
    def _edit_levels(self, rule, levels, capture):
        serializer = ComplaintSlaRuleSerializer(instance=rule, partial=True, data={"escalation_levels": [
            {"level": level, "is_enabled": True, "resolve_within_minutes": minutes} for level, minutes in levels
        ]})
        assert serializer.is_valid(), serializer.errors
        with capture(execute=True):
            serializer.save()

    def test_shorter_window_applies_to_ticket_already_waiting(self, setup, django_capture_on_commit_callbacks):
        ticket = _ticket(setup)  # L2, 60 minutes
        ComplaintTicket.objects.filter(pk=ticket.pk).update(created=timezone.now() - timedelta(minutes=5))
        self._edit_levels(setup["rule"], [(2, 1), (3, 120), (4, 240)], django_capture_on_commit_callbacks)
        ticket.refresh_from_db()
        # Counted from when it reached L2 (5 minutes ago): already overdue...
        assert ticket.next_escalation_due_at < timezone.now()
        # ...so the next sweep escalates it.
        assert check_and_escalate_overdue_tickets() == 1

    def test_escalated_ticket_counts_from_its_escalation(self, setup, django_capture_on_commit_callbacks):
        ticket = escalate_ticket(_ticket(setup), by_system=False)  # now L3, 120 minutes
        self._edit_levels(setup["rule"], [(2, 60), (3, 30), (4, 240)], django_capture_on_commit_callbacks)
        ticket.refresh_from_db()
        assert 29 <= _window_minutes(ticket) <= 30

    def test_ticket_never_placed_on_chain_joins_once_levels_exist(self, setup, django_capture_on_commit_callbacks):
        ComplaintSlaEscalationLevel.objects.all().delete()
        ticket = _ticket(setup)
        assert ticket.escalation_level == 0
        self._edit_levels(setup["rule"], [(2, 60), (3, 120)], django_capture_on_commit_callbacks)
        ticket.refresh_from_db()
        assert ticket.escalation_level == 2
        assert ticket.assigned_staff_id == setup["people"]["supervisor"].staff_unique_id


def _report(user, **params):
    from rest_framework.test import APIRequestFactory, force_authenticate

    from app.viewsets.reports.complaint_reports.complaints_report_viewset import ComplaintsReportViewSet

    request = APIRequestFactory().get("/api/v1/complaint-ticket/complaints-report/", params)
    force_authenticate(request, user=user)
    response = ComplaintsReportViewSet.as_view({"get": "list"})(request)
    assert response.status_code == 200, response.data
    return response.data


@pytest.mark.django_db
class TestComplaintsReport:
    def _admin(self):
        from app.models.superadmin_masters.auth_user import User

        return User.objects.filter(username="report-admin").first() or User.objects.create_user(
            username="report-admin", is_superuser=True
        )

    def test_kpis_breakdowns_and_register(self, setup):
        open_ticket = _ticket(setup)
        escalated = escalate_ticket(_ticket(setup), by_system=False)
        resolved = _ticket(setup, panchayat=OTHER_PANCHAYAT)
        resolved.status_id = ComplaintStatus.objects.get(status_code="RESOLVED").unique_id
        resolved.resolved_at = timezone.now()
        resolved.save()

        data = _report(self._admin())
        kpis = data["kpis"]
        assert (kpis["total"], kpis["open"], kpis["escalated"], kpis["resolved"], kpis["pending"]) == (3, 1, 1, 1, 2)
        assert kpis["sla_compliance_percent"] == pytest.approx(66.7)
        assert kpis["local_body_count"] == 2
        assert data["category_breakdown"][0] == {
            "category_id": setup["category"].unique_id, "category_name": "Garbage", "count": 3, "share_percent": 100.0,
        }
        by_area = {a["local_body_id"]: a for a in data["area_breakdown"]}
        assert (by_area[PANCHAYAT]["received"], by_area[PANCHAYAT]["pending"], by_area[PANCHAYAT]["escalated"]) == (2, 2, 1)
        assert by_area[OTHER_PANCHAYAT]["resolved"] == 1

        rows = {r["ticket_no"]: r for r in data["results"]}
        assert rows[escalated.ticket_no]["assigned_staff_name"] == "officer"
        assert rows[escalated.ticket_no]["is_breached"] is True
        assert rows[open_ticket.ticket_no]["status_bucket"] == "open"

        escalated_only = _report(self._admin(), status="escalated")
        assert [r["ticket_no"] for r in escalated_only["results"]] == [escalated.ticket_no]
        assert escalated_only["kpis"]["total"] == 3  # aggregates ignore the register tab

    def test_location_filter_and_date_range(self, setup):
        _ticket(setup)
        other = _ticket(setup, panchayat=OTHER_PANCHAYAT)
        assert _report(self._admin(), city=OTHER_PANCHAYAT)["kpis"]["total"] == 1
        assert _report(self._admin(), city=OTHER_PANCHAYAT)["results"][0]["ticket_no"] == other.ticket_no
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        assert _report(self._admin(), from_date=tomorrow, to_date=tomorrow)["kpis"]["total"] == 0

    def test_staff_only_see_their_own_tickets(self, setup):
        mine = _ticket(setup)
        _ticket(setup, panchayat=OTHER_PANCHAYAT)
        data = _report(setup["people"]["other_supervisor"])
        assert mine.ticket_no not in {r["ticket_no"] for r in data["results"]}

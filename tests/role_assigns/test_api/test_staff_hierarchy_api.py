"""Staff Hierarchy master + the Staff Head dropdown it drives.

Writes are exercised through the serializer rather than POST/PUT: the test
database has no staff_audit table, which AuditViewSetMixin writes to on
every create/update (see tests/superadmin_masters/test_api/test_state_cache.py).
"""
import jwt
import pytest
from django.conf import settings
from django.core.cache import caches
from rest_framework.test import APIClient

from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.models.superadmin.role_management.staffHierarchy import StaffHierarchy
from app.models.superadmin.role_management.userType import UserType
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin_masters.auth_user import User
from app.serializers.superadmin.role_management.staffhierarchy_serializer import StaffHierarchySerializer

BASE = "/api/v1/role-assigns/staff-hierarchy/"
HEADS = "/api/v1/user-creations/staffcreation/staff-head-options/"


@pytest.fixture(autouse=True)
def _clear_app_cache():
    caches["app_cache"].clear()
    yield
    caches["app_cache"].clear()


@pytest.fixture
def api_client(db):
    user = User.objects.create_user(username="hierarchy-tester", is_superuser=True)
    token = jwt.encode({"unique_id": user.unique_id}, settings.SECRET_KEY, algorithm="HS256")
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


@pytest.fixture
def roles(db):
    usertype = UserType.objects.create(name="government")

    def make(name, level):
        return GovernmentStaffUserType.objects.create(
            name=name, level=level, usertype_id=usertype.unique_id
        )

    return {
        "driver": make("govt_panchayat_driver", "panchayat"),
        "supervisor": make("govt_panchayat_supervisor", "panchayat"),
        "district_officer": make("govt_district_officer", "district"),
        "state_admin": make("govt_state_admin", "state"),
    }


def _staff(username, role, **geo):
    return Staffcreation.objects.create(
        username=username,
        employee_name=username,
        governmentusertype_id=role.unique_id,
        active_status=True,
        **geo,
    )


def _save(data, instance=None):
    serializer = StaffHierarchySerializer(instance=instance, data=data, partial=instance is not None)
    serializer.is_valid(raise_exception=False)
    return serializer


@pytest.mark.django_db
class TestStaffHierarchyValidation:
    def test_create_and_list_resolves_role_names(self, api_client, roles):
        serializer = _save({
            "governmentusertype_id": roles["driver"].unique_id,
            "reports_to_governmentusertype_id": roles["supervisor"].unique_id,
            "hierarchy_level": 1,
        })
        assert serializer.is_valid(), serializer.errors
        entry = serializer.save()

        resp = api_client.get(BASE, {"page": 1, "limit": 10})
        assert resp.status_code == 200
        row = next(item for item in resp.json()["results"] if item["unique_id"] == entry.unique_id)
        assert row["governmentusertype_name"] == "Panchayat Driver"
        assert row["governmentusertype_level"] == "Panchayat"
        assert row["reports_to_governmentusertype_name"] == "Panchayat Supervisor"

    def test_blank_reports_to_is_top_of_chain(self, roles):
        serializer = _save({
            "governmentusertype_id": roles["district_officer"].unique_id,
            "reports_to_governmentusertype_id": "",
        })
        assert serializer.is_valid(), serializer.errors
        assert serializer.save().reports_to_governmentusertype_id is None

    def test_rejects_self_reference(self, roles):
        role_id = roles["driver"].unique_id
        serializer = _save({
            "governmentusertype_id": role_id,
            "reports_to_governmentusertype_id": role_id,
        })
        assert not serializer.is_valid()
        assert "cannot report to itself" in str(serializer.errors)

    def test_rejects_cycle(self, roles):
        StaffHierarchy.objects.create(
            governmentusertype_id=roles["driver"].unique_id,
            reports_to_governmentusertype_id=roles["supervisor"].unique_id,
        )
        serializer = _save({
            "governmentusertype_id": roles["supervisor"].unique_id,
            "reports_to_governmentusertype_id": roles["driver"].unique_id,
        })
        assert not serializer.is_valid()
        assert "reporting cycle" in str(serializer.errors)

    def test_rejects_duplicate_role_but_allows_after_delete(self, roles):
        existing = StaffHierarchy.objects.create(governmentusertype_id=roles["driver"].unique_id)
        data = {"governmentusertype_id": roles["driver"].unique_id}
        assert not _save(data).is_valid()

        existing.delete()
        assert _save(data).is_valid()

    def test_rejects_unknown_role(self, roles):
        assert not _save({"governmentusertype_id": "GOVTUSRTYPE-missing"}).is_valid()


@pytest.mark.django_db
class TestStaffHierarchyList:
    @pytest.fixture
    def entries(self, roles):
        driver = StaffHierarchy.objects.create(
            governmentusertype_id=roles["driver"].unique_id,
            reports_to_governmentusertype_id=roles["supervisor"].unique_id,
            hierarchy_level=1,
        )
        supervisor = StaffHierarchy.objects.create(
            governmentusertype_id=roles["supervisor"].unique_id,
            reports_to_governmentusertype_id=roles["district_officer"].unique_id,
            hierarchy_level=2,
        )
        officer = StaffHierarchy.objects.create(
            governmentusertype_id=roles["district_officer"].unique_id,
            hierarchy_level=3,
            is_active=False,
        )
        return driver, supervisor, officer

    def _ids(self, resp):
        assert resp.status_code == 200, resp.content
        return [row["unique_id"] for row in resp.json()["results"]]

    def test_paginates_with_page_and_limit(self, api_client, entries):
        resp = api_client.get(BASE, {"page": 2, "limit": 2, "ordering": "hierarchy_level"})
        assert resp.json()["count"] == 3
        assert self._ids(resp) == [entries[2].unique_id]

    def test_ordering_descending(self, api_client, entries):
        resp = api_client.get(BASE, {"page": 1, "limit": 10, "ordering": "-hierarchy_level"})
        assert self._ids(resp) == [e.unique_id for e in reversed(entries)]

    def test_search_matches_role_label_on_either_side(self, api_client, entries):
        driver, supervisor, _ = entries
        resp = api_client.get(BASE, {"page": 1, "limit": 10, "search": "Supervisor"})
        assert set(self._ids(resp)) == {driver.unique_id, supervisor.unique_id}

    def test_search_matches_level_label(self, api_client, entries):
        _, supervisor, officer = entries
        resp = api_client.get(BASE, {"page": 1, "limit": 10, "search": "district"})
        assert set(self._ids(resp)) == {supervisor.unique_id, officer.unique_id}

    def test_status_filter(self, api_client, entries):
        resp = api_client.get(BASE, {"page": 1, "limit": 10, "is_active": "false"})
        assert self._ids(resp) == [entries[2].unique_id]


@pytest.mark.django_db
class TestStaffHeadOptions:
    def _heads(self, api_client, role, **params):
        resp = api_client.get(HEADS, {"governmentusertype_id": role.unique_id, **params})
        assert resp.status_code == 200, resp.content
        return {row["employee_name"] for row in resp.json()}

    def test_configured_chain_overrides_legacy_rule(self, api_client, roles):
        _staff("same_panchayat_supervisor", roles["supervisor"], district_id="D1", panchayat_id="P1")
        _staff("district_officer", roles["district_officer"], district_id="D1")
        StaffHierarchy.objects.create(
            governmentusertype_id=roles["driver"].unique_id,
            reports_to_governmentusertype_id=roles["district_officer"].unique_id,
        )

        heads = self._heads(api_client, roles["driver"], district_id="D1", panchayat_id="P1")
        assert heads == {"district_officer"}

    def test_heads_must_cover_the_staff_area(self, api_client, roles):
        _staff("sup_p1", roles["supervisor"], district_id="D1", panchayat_id="P1")
        _staff("sup_p2", roles["supervisor"], district_id="D1", panchayat_id="P2")
        _staff("sup_other_district", roles["supervisor"], district_id="D2", panchayat_id="P9")
        StaffHierarchy.objects.create(
            governmentusertype_id=roles["driver"].unique_id,
            reports_to_governmentusertype_id=roles["supervisor"].unique_id,
        )

        heads = self._heads(api_client, roles["driver"], district_id="D1", panchayat_id="P1")
        assert heads == {"sup_p1"}

    def test_top_of_chain_returns_super_admin_only(self, api_client, roles):
        _staff("sup_p1", roles["supervisor"], panchayat_id="P1")
        StaffHierarchy.objects.create(governmentusertype_id=roles["district_officer"].unique_id)

        heads = self._heads(api_client, roles["district_officer"], district_id="D1")
        assert heads == {"Super Admin"}

    def test_inactive_entry_falls_back_to_legacy_rule(self, api_client, roles):
        _staff("sup_p1", roles["supervisor"], panchayat_id="P1")
        _staff("district_officer", roles["district_officer"])
        StaffHierarchy.objects.create(
            governmentusertype_id=roles["driver"].unique_id,
            reports_to_governmentusertype_id=roles["district_officer"].unique_id,
            is_active=False,
        )

        heads = self._heads(api_client, roles["driver"], panchayat_id="P1")
        assert heads == {"sup_p1"}


@pytest.fixture
def geo(db):
    from app.models.masters.areatype import AreaType
    from app.models.masters.district import District
    from app.models.masters.panchayat import Panchayat
    from app.models.superadmin.common_masters.continent import Continent
    from app.models.superadmin.common_masters.country import Country
    from app.models.superadmin.common_masters.state import State

    continent = Continent.objects.create(name="Asia")
    country = Country.objects.create(continent_id=continent.unique_id, name="India")
    state = State.objects.create(
        continent_id=continent.unique_id, country_id=country.unique_id, name="Tamil Nadu"
    )

    def district(name):
        return District.objects.create(
            continent_id=continent.unique_id,
            country_id=country.unique_id,
            state_id=state.unique_id,
            name=name,
        )

    erode, salem = district("Erode"), district("Salem")
    rural = AreaType.objects.create(
        state_id=state.unique_id, district_id=erode.unique_id, name="Rural Local Body"
    )
    panchayat = Panchayat.objects.create(
        state_id=state.unique_id,
        district_id=erode.unique_id,
        area_type_id=rural.unique_id,
        panchayat_name="Kavindapadi",
    )
    return {
        "country": country, "state": state, "erode": erode, "salem": salem,
        "rural": rural, "panchayat": panchayat,
    }


@pytest.mark.django_db
class TestStaffHierarchyScope:
    def test_local_body_fills_in_parent_locations(self, roles, geo):
        serializer = _save({
            "governmentusertype_id": roles["driver"].unique_id,
            "reports_to_governmentusertype_id": roles["supervisor"].unique_id,
            "panchayat_id": geo["panchayat"].unique_id,
        })
        assert serializer.is_valid(), serializer.errors
        entry = serializer.save()

        assert entry.country_id == geo["country"].unique_id
        assert entry.state_id == geo["state"].unique_id
        assert entry.district_id == geo["erode"].unique_id
        assert entry.area_type_id == geo["rural"].unique_id
        data = StaffHierarchySerializer(entry).data
        assert data["scope_label"] == "India › Tamil Nadu › Erode › Rural Local Body › Kavindapadi"
        assert data["scope_level"] == "Panchayat"

    def test_rejects_location_outside_selected_parent(self, roles, geo):
        serializer = _save({
            "governmentusertype_id": roles["driver"].unique_id,
            "district_id": geo["salem"].unique_id,
            "panchayat_id": geo["panchayat"].unique_id,
        })
        assert not serializer.is_valid()
        assert "panchayat_id" in serializer.errors

    def test_same_role_allowed_once_per_location(self, roles, geo):
        role_id = roles["driver"].unique_id
        StaffHierarchy.objects.create(governmentusertype_id=role_id)

        kavindapadi = {"governmentusertype_id": role_id, "panchayat_id": geo["panchayat"].unique_id}
        serializer = _save(kavindapadi)
        assert serializer.is_valid(), serializer.errors
        serializer.save()

        assert not _save(kavindapadi).is_valid()

    def test_cycle_in_narrower_area_is_rejected(self, roles, geo):
        serializer = _save({
            "governmentusertype_id": roles["supervisor"].unique_id,
            "reports_to_governmentusertype_id": roles["driver"].unique_id,
            "panchayat_id": geo["panchayat"].unique_id,
        })
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        # Fine on its own everywhere else, but in Kavindapadi it would close
        # driver -> supervisor -> driver.
        serializer = _save({
            "governmentusertype_id": roles["driver"].unique_id,
            "reports_to_governmentusertype_id": roles["supervisor"].unique_id,
        })
        assert not serializer.is_valid()
        assert "reporting cycle" in str(serializer.errors)

    @pytest.mark.parametrize(
        "role_key, location",
        [
            ("district_officer", "panchayat"),  # local body takes only its own level
            ("driver", "erode"),                # district takes only district roles
            ("district_officer", "state"),      # state takes only state roles
        ],
    )
    def test_location_admits_only_its_own_level(self, roles, geo, role_key, location):
        field = {"panchayat": "panchayat_id", "erode": "district_id", "state": "state_id"}[location]
        serializer = _save({
            "governmentusertype_id": roles[role_key].unique_id,
            field: geo[location].unique_id,
        })
        assert not serializer.is_valid()
        assert "governmentusertype_id" in serializer.errors

    def test_matching_level_roles_are_accepted(self, roles, geo):
        for role_key, field, location in [
            ("state_admin", "state_id", "state"),
            ("district_officer", "district_id", "erode"),
            ("driver", "panchayat_id", "panchayat"),
        ]:
            serializer = _save({
                "governmentusertype_id": roles[role_key].unique_id,
                field: geo[location].unique_id,
            })
            assert serializer.is_valid(), (role_key, serializer.errors)

    def test_cannot_report_to_a_narrower_level(self, roles):
        serializer = _save({
            "governmentusertype_id": roles["district_officer"].unique_id,
            "reports_to_governmentusertype_id": roles["supervisor"].unique_id,
        })
        assert not serializer.is_valid()
        assert "reports_to_governmentusertype_id" in serializer.errors

    def test_panchayat_union_location_admits_only_union_roles(self, roles, geo):
        from app.models.masters.panchayat_union import PanchayatUnion

        union = PanchayatUnion.objects.create(
            state_id=geo["state"].unique_id,
            district_id=geo["erode"].unique_id,
            area_type_id=geo["rural"].unique_id,
            union_name="Bhavani",
        )
        serializer = _save({
            "governmentusertype_id": roles["driver"].unique_id,
            "panchayat_union_id": union.unique_id,
        })
        assert not serializer.is_valid()
        assert "governmentusertype_id" in serializer.errors

    def test_panchayat_role_cannot_report_to_union_role(self, roles):
        union_admin = GovernmentStaffUserType.objects.create(
            name="govt_panchayat_union_admin",
            level="panchayat_union",
            usertype_id=roles["driver"].usertype_id,
        )
        serializer = _save({
            "governmentusertype_id": roles["supervisor"].unique_id,
            "reports_to_governmentusertype_id": union_admin.unique_id,
        })
        assert not serializer.is_valid()
        assert "reports_to_governmentusertype_id" in serializer.errors

    def test_list_filters_by_district(self, api_client, roles, geo):
        StaffHierarchy.objects.create(governmentusertype_id=roles["driver"].unique_id)
        erode_row = StaffHierarchy.objects.create(
            governmentusertype_id=roles["driver"].unique_id, district_id=geo["erode"].unique_id
        )
        resp = api_client.get(BASE, {"page": 1, "limit": 10, "district_id": geo["erode"].unique_id})
        assert [row["unique_id"] for row in resp.json()["results"]] == [erode_row.unique_id]


@pytest.mark.django_db
class TestStaffHeadOptionsByLocation:
    def _heads(self, api_client, role, **params):
        resp = api_client.get(HEADS, {"governmentusertype_id": role.unique_id, **params})
        assert resp.status_code == 200, resp.content
        return {row["employee_name"] for row in resp.json()}

    @pytest.fixture
    def chains(self, roles, geo):
        state_id = geo["state"].unique_id
        erode_id = geo["erode"].unique_id
        salem_id = geo["salem"].unique_id
        panchayat_id = geo["panchayat"].unique_id
        _staff("kavindapadi_supervisor", roles["supervisor"],
               state_id=state_id, district_id=erode_id, panchayat_id=panchayat_id)
        _staff("erode_officer", roles["district_officer"], state_id=state_id, district_id=erode_id)
        _staff("salem_officer", roles["district_officer"], state_id=state_id, district_id=salem_id)
        _staff("state_admin", roles["state_admin"], state_id=state_id)

        rows = [
            # Everywhere: driver -> district officer; district officer -> top.
            {"governmentusertype_id": roles["driver"].unique_id,
             "reports_to_governmentusertype_id": roles["district_officer"].unique_id},
            {"governmentusertype_id": roles["district_officer"].unique_id},
            # Kavindapadi only: driver -> supervisor.
            {"governmentusertype_id": roles["driver"].unique_id,
             "reports_to_governmentusertype_id": roles["supervisor"].unique_id,
             "panchayat_id": panchayat_id},
            # Erode only: district officer -> state admin.
            {"governmentusertype_id": roles["district_officer"].unique_id,
             "reports_to_governmentusertype_id": roles["state_admin"].unique_id,
             "district_id": erode_id},
        ]
        for data in rows:
            serializer = _save(data)
            assert serializer.is_valid(), serializer.errors
            serializer.save()

    def test_panchayat_row_overrides_default(self, api_client, roles, geo, chains):
        heads = self._heads(api_client, roles["driver"], panchayat_id=geo["panchayat"].unique_id)
        assert heads == {"kavindapadi_supervisor"}

    def test_other_area_uses_default(self, api_client, roles, geo, chains):
        heads = self._heads(api_client, roles["driver"], district_id=geo["salem"].unique_id)
        assert heads == {"salem_officer"}

    def test_district_row_overrides_default_for_district_roles(self, api_client, roles, geo, chains):
        assert self._heads(
            api_client, roles["district_officer"], district_id=geo["erode"].unique_id
        ) == {"state_admin"}
        assert self._heads(
            api_client, roles["district_officer"], district_id=geo["salem"].unique_id
        ) == {"Super Admin"}

"""
Shared fixtures and factories for all unit tests.

Database: tests use SQLite in-memory (overridden via django_db_setup).
This avoids MySQL FK-creation issues and makes tests fast and portable.
"""
import pytest


# ─────────────────────────────────────────────
# Tenant fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def company(db):
    from app.models.superadmin_masters.company import Company
    return Company.objects.create(name="Test Company", description="A test company")


@pytest.fixture
def project(db, company):
    from app.models.superadmin_masters.project import Project
    return Project.objects.create(name="Test Project", company_id=company)


# ─────────────────────────────────────────────
# Geographic hierarchy fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def continent(db):
    from app.models.superadmin.common_masters.continent import Continent
    return Continent.objects.create(name="Asia")


@pytest.fixture
def country(db, continent):
    from app.models.superadmin.common_masters.country import Country
    return Country.objects.create(
        name="India",
        continent_id=continent,
        currency="INR",
        mob_code="+91",
    )


@pytest.fixture
def state(db, continent, country):
    from app.models.superadmin.common_masters.state import State
    return State.objects.create(
        name="Tamil Nadu",
        label="TN",
        continent_id=continent,
        country_id=country,
    )


@pytest.fixture
def district(db, continent, country, state):
    from app.models.masters.district import District
    return District.objects.create(
        name="Chennai",
        continent_id=continent,
        country_id=country,
        state_id=state,
    )


@pytest.fixture
def city(db, continent, country, state, district):
    from app.models.masters.city import City
    return City.objects.create(
        name="Chennai City",
        continent_id=continent,
        country_id=country,
        state_id=state,
        district_id=district,
    )


@pytest.fixture
def area_type(db, state, district, city):
    from app.models.masters.areatype import AreaType
    return AreaType.objects.create(
        name="Urban",
        state_id=state,
        district_id=district,
        city_id=city,
    )


@pytest.fixture
def zone(db, state, district, city):
    from app.models.masters.zone import Zone
    return Zone.objects.create(
        zone_name="Zone 1",
        state_id=state,
        district_id=district,
        city_id=city,
    )


@pytest.fixture
def corporation(db, state, district):
    from app.models.masters.areatype import AreaType
    from app.models.masters.corporation import Corporation

    area_type = AreaType.objects.create(
        state_id=state,
        district_id=district,
        name="Urban Local Body",
    )
    return Corporation.objects.create(
        state_id=state,
        district_id=district,
        area_type_id=area_type,
        corporation_name="Test Corporation",
    )


@pytest.fixture
def ward(db, state, district, corporation):
    from app.models.masters.ward import Ward
    return Ward.objects.create(
        ward_name="Ward 1",
        state=state,
        district=district,
        area_type=corporation.area_type_id,
        corporation=corporation,
    )


# ─────────────────────────────────────────────
# Role / user fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def user_type(db):
    from app.models.superadmin.role_management.userType import UserType
    return UserType.objects.create(name="Staff")


@pytest.fixture
def superuser(db):
    from app.models.superadmin_masters.auth_user import User
    return User.objects.create_superuser(
        username="admin_test",
        password="testpass123",
    )


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, superuser):
    """APIClient authenticated as superuser via JWT with unique_id claim."""
    from rest_framework_simplejwt.tokens import AccessToken
    token = AccessToken.for_user(superuser)
    token["unique_id"] = superuser.unique_id  # required by JWTUserAuthentication
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client

"""Unit tests for CustomerCreation model — CRUD + constraints."""
import pytest
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="Customer Panchayat",
        company_id=company, project_id=project,
        state_id=state, district_id=district, city_id=city,
    )


@pytest.fixture
def prop(db):
    return Property.objects.create(property_name="Residential")


@pytest.fixture
def sub_prop(db, prop):
    return SubProperty.objects.create(sub_property_name="Apartment", property_id=prop)


@pytest.fixture
def customer(db, company, project, continent, country, state, district, city, zone, ward, panchayat, prop, sub_prop):
    return CustomerCreation.objects.create(
        customer_name="Alice",
        contact_no="9876543210",
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="Aadhar",
        id_no="1234-5678-9012",
        company_id=company, project_id=project,
        country=country, state=state, district=district,
        city=city, zone=zone, ward=ward,
        panchayat_id=panchayat,
        property_ref=prop, sub_property=sub_prop,
    )


@pytest.mark.django_db
class TestCustomerCreationCreate:
    def test_basic_create(self, customer):
        assert customer.customer_name == "Alice"

    def test_unique_id_prefix(self, customer):
        assert customer.unique_id.startswith("CUS-")

    def test_foreign_key_company(self, customer, company):
        assert customer.company_id == company

    def test_optional_fields_null(self, customer):
        assert customer.building_no is None
        assert customer.email is None


@pytest.mark.django_db
class TestCustomerCreationDefaults:
    def test_is_active_default_true(self, customer):
        assert customer.is_active is True

    def test_is_deleted_default_false(self, customer):
        assert customer.is_deleted is False


@pytest.mark.django_db
class TestCustomerCreationSoftDelete:
    def test_soft_delete(self, customer):
        customer.delete()
        customer.refresh_from_db()
        assert customer.is_deleted is True
        assert customer.is_active is False


@pytest.mark.django_db
class TestCustomerCreationUpdate:
    def test_update_name(self, customer):
        customer.customer_name = "Bob"
        customer.save()
        customer.refresh_from_db()
        assert customer.customer_name == "Bob"

    def test_update_contact(self, customer):
        customer.contact_no = "9999999999"
        customer.save()
        customer.refresh_from_db()
        assert customer.contact_no == "9999999999"

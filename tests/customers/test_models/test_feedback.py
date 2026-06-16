"""Unit tests for FeedBack model — CRUD + constraints."""
import pytest
from app.models.customers.feedback import FeedBack
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


@pytest.fixture
def panchayat(db, company, project, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="FB Panchayat",
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
class TestFeedBackCreate:
    def test_basic_create(self, customer, company, project):
        fb = FeedBack.objects.create(category="Satisfied", feedback_details="Good", customer=customer, company_id=company, project_id=project)
        assert fb.category == "Satisfied"

    def test_unique_id_prefix(self, customer, company, project):
        fb = FeedBack.objects.create(category="Poor", customer=customer, company_id=company, project_id=project)
        assert fb.unique_id.startswith("FEED-")

    def test_foreign_key_customer(self, customer, company, project):
        fb = FeedBack.objects.create(category="Excellent", customer=customer, company_id=company, project_id=project)
        assert fb.customer == customer


@pytest.mark.django_db
class TestFeedBackDefaults:
    def test_is_active_default_true(self, customer, company, project):
        fb = FeedBack.objects.create(category="Good", customer=customer, company_id=company, project_id=project)
        assert fb.is_active is True

    def test_is_deleted_default_false(self, customer, company, project):
        fb = FeedBack.objects.create(category="Average", customer=customer, company_id=company, project_id=project)
        assert fb.is_deleted is False

    def test_optional_details_nullable(self, customer, company, project):
        fb = FeedBack.objects.create(category="Satisfied", customer=customer, company_id=company, project_id=project)
        assert fb.feedback_details is None


@pytest.mark.django_db
class TestFeedBackSoftDelete:
    def test_soft_delete(self, customer, company, project):
        fb = FeedBack.objects.create(category="Not Satisfied", customer=customer, company_id=company, project_id=project)
        fb.delete()
        fb.refresh_from_db()
        assert fb.is_deleted is True
        assert fb.is_active is False


@pytest.mark.django_db
class TestFeedBackUpdate:
    def test_update_category(self, customer, company, project):
        fb = FeedBack.objects.create(category="Old Cat", customer=customer, company_id=company, project_id=project)
        fb.category = "New Cat"
        fb.save()
        fb.refresh_from_db()
        assert fb.category == "New Cat"

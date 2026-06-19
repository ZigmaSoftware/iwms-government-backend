"""Unit tests for FeedBack model — CRUD + constraints."""
import pytest
from app.models.customers.feedback import FeedBack
from app.models.customers.customercreation import CustomerCreation
from app.models.masters.panchayat import Panchayat
from app.models.waste_types.property import Property
from app.models.waste_types.subproperty import SubProperty


@pytest.fixture
def panchayat(db, state, district, city):
    return Panchayat.objects.create(
        panchayat_name="FB Panchayat",
        state_id=state, district_id=district, city_id=city,
    )


@pytest.fixture
def prop(db):
    return Property.objects.create(property_name="Residential")


@pytest.fixture
def sub_prop(db, prop):
    return SubProperty.objects.create(sub_property_name="Apartment", property_id=prop)


@pytest.fixture
def customer(db, continent, country, state, district, city, zone, ward, panchayat, prop, sub_prop):
    return CustomerCreation.objects.create(
        customer_name="Alice",
        contact_no="9876543210",
        pincode="600001",
        latitude="13.0827",
        longitude="80.2707",
        id_proof_type="AADHAAR",
        id_no="1234-5678-9012",
        country=country, state=state, district=district,
        city=city, zone=zone, ward=ward,
        panchayat_id=panchayat,
        property_ref=prop, sub_property=sub_prop,
    )


@pytest.mark.django_db
class TestFeedBackCreate:
    def test_basic_create(self, customer):
        fb = FeedBack.objects.create(category="Satisfied", feedback_details="Good", customer=customer)
        assert fb.category == "Satisfied"

    def test_unique_id_prefix(self, customer):
        fb = FeedBack.objects.create(category="Poor", customer=customer)
        assert fb.unique_id.startswith("FEED-")

    def test_foreign_key_customer(self, customer):
        fb = FeedBack.objects.create(category="Excellent", customer=customer)
        assert fb.customer == customer


@pytest.mark.django_db
class TestFeedBackDefaults:
    def test_is_active_default_true(self, customer):
        fb = FeedBack.objects.create(category="Good", customer=customer)
        assert fb.is_active is True

    def test_is_deleted_default_false(self, customer):
        fb = FeedBack.objects.create(category="Average", customer=customer)
        assert fb.is_deleted is False

    def test_optional_details_nullable(self, customer):
        fb = FeedBack.objects.create(category="Satisfied", customer=customer)
        assert fb.feedback_details is None


@pytest.mark.django_db
class TestFeedBackSoftDelete:
    def test_soft_delete(self, customer):
        fb = FeedBack.objects.create(category="Not Satisfied", customer=customer)
        fb.delete()
        fb.refresh_from_db()
        assert fb.is_deleted is True
        assert fb.is_active is False


@pytest.mark.django_db
class TestFeedBackUpdate:
    def test_update_category(self, customer):
        fb = FeedBack.objects.create(category="Old Cat", customer=customer)
        fb.category = "New Cat"
        fb.save()
        fb.refresh_from_db()
        assert fb.category == "New Cat"

"""Customer forms can select only the customer mobile surface."""
import pytest
from rest_framework import serializers

from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.masters.district import District
from app.models.masters.panchayat import Panchayat
from app.models.masters.ward import Ward
from app.models.superadmin.common_masters.state import State
from app.serializers.masters.customer_masters.customercreation_serializer import CustomerCreationSerializer


@pytest.mark.parametrize('surface', ['driver', 'operator', 'supervisor', 'none', '', None])
def test_customer_rejects_other_mobile_app_surfaces(surface):
    serializer = CustomerCreationSerializer(data={'app_module': surface}, partial=True)
    assert not serializer.is_valid()
    assert 'app_module' in serializer.errors


def test_customer_mobile_app_defaults_to_customer():
    field = CustomerCreationSerializer().fields['app_module']
    assert field.run_validation(serializers.empty) == 'citizen'
    assert list(field.choices) == ['citizen']


@pytest.mark.django_db
@pytest.mark.parametrize('payload', [{'app_module': 'citizen'}, {'customer_name': 'Updated customer'}])
def test_customer_update_persists_customer_app_even_when_field_is_omitted(payload):
    state = State.objects.create(name='Test State')
    district = District.objects.create(name='Test District', state_id=state.unique_id)
    panchayat = Panchayat.objects.create(panchayat_name='Test Panchayat', state_id=state.unique_id, district_id=district.unique_id)
    ward = Ward.objects.create(ward_name='Test Ward', panchayat_id=panchayat.unique_id)
    customer = CustomerCreation.objects.create(customer_name='Customer', contact_no='9000000001',
        state_id=state.unique_id, district_id=district.unique_id, panchayat_id=panchayat.unique_id,
        ward_id=ward.unique_id, app_module='driver')
    serializer = CustomerCreationSerializer(customer, data=payload, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    customer.refresh_from_db()
    assert customer.app_module == 'citizen'
    assert serializer.data['app_module'] == 'citizen'

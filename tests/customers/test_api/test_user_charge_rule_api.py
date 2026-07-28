"""API tests for UserChargeRule endpoint — CRUD operations."""
import pytest

BASE = "/api/v1/customer-masters/user-charge-rules/"


@pytest.mark.django_db
class TestUserChargeRuleAPIList:
    def test_list_unauthenticated_returns_401(self, api_client):
        resp = api_client.get(BASE)
        assert resp.status_code in (401, 403)

    def test_list_authenticated_returns_200(self, auth_client):
        resp = auth_client.get(BASE)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestUserChargeRuleAPICreate:
    def test_create_returns_success(self, auth_client, company, project):
        from app.models.masters.waste_masters.property import Property
        from app.models.masters.waste_masters.subproperty import SubProperty
        prop = Property.objects.create(property_name="Residential")
        sub = SubProperty.objects.create(property_id=prop, sub_property_name="Flat")
        resp = auth_client.post(
            BASE,
            {
                "company_id": company.unique_id,
                "project_id": project.unique_id,
                "property_id": prop.pk,
                "subproperty_id": sub.pk,
                "min_sqmtr_value": "0.00",
                "max_sqmtr_value": "100.00",
                "amount": "50.00",
            },
            format="json",
        )
        assert resp.status_code in (200, 201)


@pytest.mark.django_db
class TestUserChargeRuleAPIRetrieve:
    def test_retrieve_nonexistent_returns_404(self, auth_client):
        resp = auth_client.get(f"{BASE}UCR-NOTEXIST/")
        assert resp.status_code in (404, 400)

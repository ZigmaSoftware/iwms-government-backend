import pytest

from app.utils.roles import is_admin_portal_role


@pytest.mark.parametrize(
    "role",
    ["superadmin", "company_admin", "company_project_admin", "contractor_admin", "govt_state_admin", " Company_Admin "],
)
def test_admin_roles_open_admin_portal(role):
    assert is_admin_portal_role(role) is True


@pytest.mark.parametrize(
    "role",
    [None, "", "company_user", "company_supervisor", "govt_district_officer", "platform", "state_leader"],
)
def test_other_roles_do_not(role):
    assert is_admin_portal_role(role) is False

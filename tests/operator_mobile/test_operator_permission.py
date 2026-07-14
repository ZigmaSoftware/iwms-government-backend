from types import SimpleNamespace

from app.permissions.operator_permission import IsOperatorRole


def _request_for_role(role_name):
    role = SimpleNamespace(name=role_name)
    user = SimpleNamespace(
        is_authenticated=True,
        staffusertype_id=role,
        governmentusertype_id=None,
        contractorusertype_id=None,
    )
    return SimpleNamespace(user=user)


def test_operator_permission_accepts_field_staff_role():
    assert IsOperatorRole().has_permission(_request_for_role("field_staff"), None)


def test_operator_permission_rejects_non_collection_role():
    assert not IsOperatorRole().has_permission(_request_for_role("accountant"), None)

"""
Central resolution of a user's effective business role across the three role
axes and the semantic predicates the gating code needs.

A `Staffcreation` carries three nullable role FKs — `staffusertype_id`
(company roles), `contractorusertype_id`, and `governmentusertype_id`
(government roles, e.g. ``govt_corporation_admin`` / ``govt_corporation_supervisor``).
Exactly one is set for a given staff member.

Historically the gating code (``app/permissions/platform.py`` and the string
matches in ``daily_trip_assignment_viewset`` / ``staff_template_viewset``) read
only ``staffusertype_id.name`` and compared it against a bare ``"supervisor"`` /
``"admin"`` literal. That silently ignored every government role — a
``govt_corporation_admin`` or ``govt_corporation_supervisor`` resolved to an
empty role name and was denied admin/supervisor privileges. These helpers look
at all three axes and match by role *shape* so both the company roles
(``company_admin`` / ``company_supervisor``) and the government roles
(``govt_<level>_admin`` / ``govt_<level>_supervisor``) are recognised.
"""

ROLE_FK_ATTRS = (
    "staffusertype_id",
    "contractorusertype_id",
    "governmentusertype_id",
)

# Plain (non-prefixed) admin role names across the company/legacy axes.
ADMIN_ROLE_NAMES = {"admin", "company_admin", "company admin"}

# Plain (non-prefixed) supervisor role names across the company/legacy axes.
SUPERVISOR_ROLE_NAMES = {"supervisor", "company_supervisor", "company supervisor"}


def effective_role_name(user):
    """Return the lowercased role name from whichever role FK is populated on
    `user`, or "" if none. Order: staff → contractor → government."""
    if not user:
        return ""
    for attr in ROLE_FK_ATTRS:
        name = getattr(getattr(user, attr, None), "name", None)
        if name:
            return name.strip().lower()
    return ""


def is_super_admin(user):
    return bool(user and getattr(user, "is_superuser", False))


def is_admin_role(user):
    """True for a company admin (``admin``/``company_admin``) or any government
    admin (``govt_<level>_admin``)."""
    role = effective_role_name(user)
    if not role:
        return False
    if role in ADMIN_ROLE_NAMES:
        return True
    return role.startswith("govt_") and role.endswith("_admin")


def is_supervisor_role(user):
    """True for a company supervisor or any government supervisor
    (``govt_<level>_supervisor``, e.g. ``govt_corporation_supervisor``)."""
    role = effective_role_name(user)
    if not role:
        return False
    if role in SUPERVISOR_ROLE_NAMES:
        return True
    return role.startswith("govt_") and role.endswith("_supervisor")


def can_manage_trips(user):
    """Who may create/edit/approve trips & daily trips: super admin, any admin,
    or any supervisor. (Screen-level write access is still enforced separately
    by the module permission middleware / UserScreenPermission rows.)"""
    return is_super_admin(user) or is_admin_role(user) or is_supervisor_role(user)

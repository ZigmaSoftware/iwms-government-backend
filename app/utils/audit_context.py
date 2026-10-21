"""
Resolves the actor identity (and request context) recorded on every
CommonAudit row.

Kept separate from AuditViewSetMixin so the same rules can be reused by any
non-viewset code that needs to write an audit entry.
"""

from app.utils.hierarchy import FLAT_GEO_FIELDS, copy_flat_geo


def display_name(obj):
    """
    Human-readable name for any account-like record (staff, customer,
    leader or platform user): its person name when it has one, falling back
    to first/last name, then username/email, then str().
    """
    if obj is None:
        return None

    # Staff/customer/leader records carry a person's name; platform users
    # usually only have a username. Fall back through the options rather
    # than showing blank.
    for attr in ("employee_name", "customer_name", "leader_name", "full_name", "name"):
        name = (getattr(obj, attr, None) or "").strip()
        if name:
            return name

    first = (getattr(obj, "first_name", "") or "").strip()
    last = (getattr(obj, "last_name", "") or "").strip()
    name = f"{first} {last}".strip()
    if name:
        return name

    return (
        (getattr(obj, "username", None) or "").strip()
        or (getattr(obj, "email", None) or "").strip()
        or str(obj)
    )


def resolve_actor(user):
    """
    (created_by_id, created_by_name, created_by_type) for the acting user.

    request.user can be a Staffcreation, CustomerCreation, one of the leader
    logins or a platform User (see JWTUserAuthentication), so identity is
    probed in preference order rather than assumed.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return None, "SYSTEM", "system"

    actor_id = (
        getattr(user, "staff_unique_id", None)
        or getattr(user, "unique_id", None)
        or getattr(user, "pk", None)
    )

    name = display_name(user)

    if getattr(user, "is_superuser", False):
        actor_type = "super_admin"
    elif getattr(user, "staff_unique_id", None):
        actor_type = "staff"
    elif hasattr(user, "customer_name"):
        actor_type = "customer"
    elif hasattr(user, "leader_name"):
        actor_type = "leader"
    else:
        actor_type = "user"

    return (str(actor_id) if actor_id else None), name, actor_type


def stamp_audit_geo(common_audit, source):
    """
    Copy `source`'s flat geo block onto a CommonAudit row.

    CommonAudit's geo columns are bare-named fields (attname "state",
    db_column "state_id"), while `copy_flat_geo` writes "<field>_id"
    attributes — which on this model are plain Python attributes Django
    never saves. Move them onto the real fields so the row can be scoped.
    """
    if source is None:
        return
    copy_flat_geo(common_audit, source)
    for field in FLAT_GEO_FIELDS:
        value = common_audit.__dict__.pop(f"{field}_id", None)
        if value:
            setattr(common_audit, field, value)

"""
Delete reason captured from the client on every DELETE request.

The frontend sends `delete_reason` in the DELETE body (query param also
accepted). DeleteReasonMixin validates it and publishes it through a
context variable for the duration of the request, so cascade_soft_delete()
can stamp it on the deleted row and every cascaded child without each
viewset's destroy path having to pass it through by hand.
"""
from contextvars import ContextVar

DELETE_REASON_FIELD = "delete_reason"
DELETE_REASON_MAX_LENGTH = 500

_current_delete_reason = ContextVar("current_delete_reason", default=None)


def read_delete_reason(request):
    """The stripped delete reason sent with this request, or "" when none."""
    value = None
    data = getattr(request, "data", None)
    if hasattr(data, "get"):
        value = data.get(DELETE_REASON_FIELD)
    if not value:
        params = getattr(request, "query_params", None) or getattr(request, "GET", {})
        value = params.get(DELETE_REASON_FIELD)
    return str(value).strip() if value else ""


def set_current_delete_reason(reason):
    return _current_delete_reason.set(reason)


def reset_current_delete_reason(token):
    _current_delete_reason.reset(token)


def get_current_delete_reason():
    return _current_delete_reason.get()


def cascaded_delete_reason(reason, root):
    """Reason stamped on a child row swept up by a parent's cascade, so the
    row shows which parent delete removed it."""
    text = f"{reason} (cascaded from {type(root).__name__} {root.pk})"
    return text[:DELETE_REASON_MAX_LENGTH]

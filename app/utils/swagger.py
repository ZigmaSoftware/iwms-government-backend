from typing import Optional

from drf_yasg.inspectors import SwaggerAutoSchema


GROUP_DISPLAY_NAMES = {
    "common-masters": "Common Masters",
    "masters": "Masters",
    "waste-types": "Waste Types",
    "assets": "Assets",
    "screen-managements": "Screen Management",
    "role-assigns": "Role Assign",
    "user-creations": "User Creation",
    "process": "Process",
    "login": "Login",
    "customers": "Customers",
    "complaint-ticket": "Complaint Ticketing",
    "citizen": "Citizen",
    "transport-masters": "Transport Masters",
    "audits": "Audits",
    "superadmin": "Superadmin",
    "waste-bluetooth": "Waste Bluetooth",
    "mobile": "Mobile",
}

OPERATION_ACTION_NAMES = {
    "list",
    "create",
    "retrieve",
    "update",
    "partial_update",
    "destroy",
    "metadata",
    "options",
}

BASENAME_INFO: dict[str, dict[str, object]] = {}


def register_group_basename(
    basename: str,
    group: str,
    prefix: str,
    include_group_in_prefix: bool,
) -> None:
    BASENAME_INFO[basename] = {
        "group": group,
        "prefix": prefix,
        "label": prefix.replace("-", " ").title(),
        "include_group_in_prefix": include_group_in_prefix,
    }


def _normalize_segment(segment: str) -> str:
    return segment.strip("/").lower()


def _extract_group_from_path(path: str) -> Optional[str]:
    parts = [p for p in path.split("?")[0].split("/") if p]
    for part in parts:
        normalized = _normalize_segment(part)
        if normalized == "api":
            continue
        if normalized.startswith("v") and normalized[1:].isdigit():
            continue
        if normalized in GROUP_DISPLAY_NAMES:
            return normalized
    return None


class GroupedSwaggerAutoSchema(SwaggerAutoSchema):
    """Swagger auto schema that tags endpoints by group and endpoint name."""

    def get_tags(self, operation_keys=None):
        # 1️⃣ If explicitly overridden
        override_tags = self.overrides.get("tags")
        if override_tags:
            return override_tags

        operation_keys = operation_keys or self.operation_keys or []
        basename = getattr(self.view, "basename", None)
        info = BASENAME_INFO.get(basename) if basename else None

        group = None
        prefix_label = None

        if info:
            group = info.get("group")
            prefix_label = info.get("label")

        # 2️⃣ If group not found from basename, extract from path
        if not group:
            group = _extract_group_from_path(self.path)

        # 3️⃣ Format display names
        def format_display(name: str | None) -> str | None:
            if not name:
                return None
            return GROUP_DISPLAY_NAMES.get(name, name.replace("-", " ").title())

        tags = []

        # Add GROUP tag
        group_label = format_display(group)
        if group_label:
            tags.append(group_label)

        # Add ENDPOINT tag
        if prefix_label:
            endpoint_label = format_display(prefix_label)
            if endpoint_label and endpoint_label not in tags:
                tags.append(endpoint_label)

        # Fallback (very rare)
        if not tags:
            return ["IWMS API"]

        return tags

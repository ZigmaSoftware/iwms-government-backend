"""Renders app/utils/permission_catalog.py as the frontend's TypeScript copy.

Written by `python manage.py sync_permission_catalog` (ported from
iwms-private); a test fails while the generated file differs from this output.
"""
import json
from pathlib import Path

from app.utils import permission_catalog as catalog

FRONTEND_CATALOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "iwms-government-frontend/src/generated/permissionCatalog.ts"
)

_HEADER = """\
// AUTO-GENERATED — do not edit by hand.
// Source:     iwms-government-backend/app/utils/permission_catalog.py
// Regenerate: cd iwms-government-backend && python manage.py sync_permission_catalog
//
// The one list of permission modules and screens, shared with the backend
// seeder and ModulePermissionMiddleware. Sidebar entries name their
// permission through `permissionFor`, so a module/screen that does not exist
// in the backend catalog is a TypeScript error.
"""

_FOOTER = """\
export type PermissionModule = keyof typeof PERMISSION_CATALOG;

export type PermissionScreen<M extends PermissionModule> =
  keyof (typeof PERMISSION_CATALOG)[M]["screens"] & string;

/** The permission a sidebar entry checks: one module, one or more screens. */
export const permissionFor = <M extends PermissionModule>(
  module: M,
  ...screens: [PermissionScreen<M>, ...PermissionScreen<M>[]]
): { module: M; screens: string[] } => ({ module, screens });
"""


def _q(value):
    return json.dumps(value, ensure_ascii=False)


def render_typescript():
    lines = [_HEADER, "export const PERMISSION_CATALOG = {"]
    for section, modules in catalog.SECTIONS:
        for mod in modules:
            lines.append(f"  {_q(mod['name'])}: {{")
            lines.append(f"    label: {_q(mod['label'])},")
            lines.append(f"    section: {_q(section)},")
            lines.append("    screens: {")
            for scr in mod["screens"]:
                lines.append(f"      {_q(scr['name'])}: {{ label: {_q(scr['label'])} }},")
            lines.append("    },")
            lines.append("  },")
    lines.append("} as const;")
    lines.append("")
    lines.append(
        "// Names used before every module/screen was named after the sidebar,"
    )
    lines.append("// still found in older audit records: old name -> current name.")
    for const, mapping in (
        ("LEGACY_MODULE_NAMES", catalog.LEGACY_MODULE_NAMES),
        ("LEGACY_SCREEN_NAMES", catalog.LEGACY_SCREEN_NAMES),
    ):
        lines.append(f"export const {const}: Record<string, string> = {{")
        for old, new in mapping.items():
            lines.append(f"  {_q(old)}: {_q(new)},")
        lines.append("};")
        lines.append("")
    return "\n".join(lines) + "\n" + _FOOTER

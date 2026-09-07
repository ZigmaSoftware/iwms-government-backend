"""Guards on the mobile permission wiring.

Ported from the private backend. Two things can silently drift out of step
here, and neither fails loudly — the lookup simply returns no actions, the app
gets a 403 or a permanently hidden screen, and it looks like a configuration
mistake:

  * a screen named in a visibility rule or a role template that no longer
    exists, or whose name cannot authorize its own route;
  * an app module whose surface the app does not route to.

This codebase seeds several screens under names that differ from the URL
segment their route uses (`householdcollection-events` fronts
`daily-trip-household-collections`, `secondary-bin-collection-events` fronts
`bin-collection-events`). Those are reconciled by RESOURCE_PERMISSION_ALIASES,
and these tests are what prove the reconciliation actually holds.
"""

from functools import lru_cache

import pytest

from app.middleware.module_permission_middleware import (
    MODULE_PERMISSION_ALIASES,
    MODULE_RESOURCE_ALLOWLIST,
    ModulePermissionMiddleware,
    RESOURCE_PERMISSION_ALIASES,
)
from app.utils.app_feature_grants import (
    APP_MODULE_CHOICES,
    APP_MODULE_SEED,
    APP_SURFACE_CONFIG,
    APP_SURFACE_KEYS,
    CITIZEN_APP_SCREENS,
    ROLE_SCREEN_TEMPLATES,
    SCREEN_PERMISSIONS,
    visible_screens,
)

VALID_ACTIONS = {"view", "add", "edit", "delete", "use", "export"}


@lru_cache(maxsize=1)
def _registered_routes():
    """Every (module, resource) -> viewset the router actually serves."""
    from app.urls.base_urls import router

    routes = {}
    for group, entries in router.group_map.items():
        for entry in entries:
            resource = str(entry.get("prefix") or "").split("/")[-1]
            if resource:
                routes[(group, resource)] = entry.get("viewset")
    return routes


def _resource_is_reachable(module, resource):
    """Replays the middleware's own allowlist check for this grant.

    A grant is reachable when a route exists under the module AND the
    middleware would accept it — which it decides from the URL segment *or*
    the viewset's `permission_resource` (defaulting to the class name minus
    "ViewSet"), plus that resource's aliases. All are tried, exactly as
    `process_view` does.
    """
    normalize = ModulePermissionMiddleware._normalize_permission_key

    url_modules = {module}
    for url_module, alias in MODULE_PERMISSION_ALIASES.items():
        if alias == module:
            url_modules.add(url_module)

    routes = _registered_routes()
    for url_module in url_modules:
        allowed = {
            normalize(name)
            for name in MODULE_RESOURCE_ALLOWLIST.get(url_module, set())
        }
        if not allowed:
            continue

        for (route_module, route_resource), viewset in routes.items():
            if route_module != url_module or viewset is None:
                continue

            permission_resource = getattr(
                viewset, "permission_resource", viewset.__name__.replace("ViewSet", "")
            )
            if normalize(permission_resource) not in allowed:
                continue

            # The seeded screen name must be one the middleware would match
            # for this route: the URL segment itself, the permission_resource,
            # or one of that resource's aliases.
            candidates = {route_resource, permission_resource}
            candidates.update(RESOURCE_PERMISSION_ALIASES.get(permission_resource, ()))
            if any(normalize(c) == normalize(resource) for c in candidates if c):
                return True
    return False


# ============================================================
# APP MODULE MASTER
# ============================================================

def test_every_app_module_has_a_surface_and_route():
    for entry in APP_MODULE_SEED:
        assert entry["module_key"].startswith("app-")
        assert entry["surface_key"]
        assert entry["route"].startswith("/")
        assert entry["label"]


def test_app_module_keys_and_surfaces_are_unique():
    keys = [e["module_key"] for e in APP_MODULE_SEED]
    surfaces = [e["surface_key"] for e in APP_MODULE_SEED]
    assert len(keys) == len(set(keys))
    assert len(surfaces) == len(set(surfaces))


def test_app_module_choices_cover_every_module_plus_none():
    values = {value for value, _ in APP_MODULE_CHOICES}
    assert values == set(APP_SURFACE_KEYS) | {"none"}


def test_surface_config_matches_the_master():
    assert set(APP_SURFACE_CONFIG) == set(APP_SURFACE_KEYS)


# ============================================================
# SCREEN VISIBILITY
# ============================================================

@pytest.mark.parametrize("screen_key", sorted(SCREEN_PERMISSIONS))
def test_visibility_rules_name_reachable_permissions(screen_key):
    requirement = SCREEN_PERMISSIONS[screen_key]
    if requirement is None:
        return

    module, resource, action = requirement
    assert action in VALID_ACTIONS, f"{screen_key}: unknown action '{action}'"
    assert _resource_is_reachable(module, resource), (
        f"{screen_key} is gated on '{module}/{resource}', which the middleware "
        "would never match — the screen would be permanently hidden"
    )


def test_every_screen_key_belongs_to_a_real_surface():
    for screen_key in SCREEN_PERMISSIONS:
        surface = screen_key.split(".", 1)[0]
        assert surface in APP_SURFACE_KEYS, (
            f"'{screen_key}' names surface '{surface}', which is not an app module"
        )


def test_a_screen_appears_when_its_permission_is_granted():
    permissions = {"schedule-operations": {"daily-trip-assignments": ["view"]}}
    visible = visible_screens(permissions, "supervisor")
    assert "supervisor.trips" in visible
    assert "supervisor.dashboard" in visible


def test_a_screen_is_hidden_when_its_permission_is_missing():
    permissions = {"schedule-operations": {"daily-trip-assignments": ["view"]}}
    visible = visible_screens(permissions, "supervisor")
    assert "supervisor.complaints" not in visible
    assert "supervisor.crew" not in visible


def test_screens_with_no_permission_are_always_visible():
    """Profile is the user's own — nobody should be locked out of it."""
    assert "supervisor.profile" in visible_screens({}, "supervisor")
    assert "driver.profile" in visible_screens({}, "driver")


def test_partial_grants_do_not_hide_a_screen():
    """A screen is gated on its main list permission only. Gating on every
    endpoint it reads would mean one missed tick makes a tab vanish."""
    permissions = {"schedule-operations": {"daily-trip-assignments": ["view"]}}
    assert "supervisor.trips" in visible_screens(permissions, "supervisor")


def test_module_alias_is_honoured_in_visibility():
    """`customers` is the permission name for the `customer-masters` routes."""
    permissions = {"customers": {"customercreations": ["view"]}}
    assert "supervisor.households" in visible_screens(permissions, "supervisor")


def test_citizen_screens_are_ticked_explicitly():
    granted = visible_screens({}, "citizen", citizen_screens={"app-citizen-complaints"})
    assert granted == ["citizen.complaints"]
    assert visible_screens({}, "citizen", citizen_screens=set()) == []


def test_citizen_screen_names_match_the_seeded_screens():
    for screen_key in SCREEN_PERMISSIONS:
        if not screen_key.startswith("citizen."):
            continue
        name = f"app-citizen-{screen_key.split('.', 1)[1]}"
        assert name in CITIZEN_APP_SCREENS, f"{screen_key} has no seeded screen"


# ============================================================
# ROLE TEMPLATES
# ============================================================

@pytest.mark.parametrize("role", sorted(ROLE_SCREEN_TEMPLATES))
def test_role_templates_name_reachable_screens(role):
    for module, screens in ROLE_SCREEN_TEMPLATES[role].items():
        for resource, actions in screens.items():
            assert _resource_is_reachable(module, resource), (
                f"{role}: '{module}/{resource}' is not reachable — granting "
                "this template would authorize nothing"
            )
            unknown = set(actions) - VALID_ACTIONS
            assert not unknown, f"{role}: unknown actions {unknown}"


@pytest.mark.parametrize("role", ["driver", "operator", "supervisor"])
def test_role_template_covers_every_screen_that_role_can_see(role):
    """Applying a role's defaults must actually unhide that role's screens,
    otherwise the grant succeeds and the user still opens an app with no tabs."""
    template = ROLE_SCREEN_TEMPLATES[role]
    permissions = {
        module: {screen: list(actions) for screen, actions in screens.items()}
        for module, screens in template.items()
    }
    visible = visible_screens(permissions, role)

    expected = [key for key in SCREEN_PERMISSIONS if key.startswith(f"{role}.")]
    missing = sorted(set(expected) - set(visible))
    assert not missing, f"{role}: these screens would stay hidden: {missing}"

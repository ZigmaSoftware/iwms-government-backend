from app.management.commands.seeders.base import BaseSeeder
from app.models.superadmin.screen_management.mainscreentype import MainScreenType
from app.models.superadmin.screen_management.mainscreen import MainScreen
from app.models.superadmin.screen_management.userscreen import UserScreen
from app.models.superadmin.screen_management.userscreenaction import UserScreenAction
from app.utils.permission_catalog import INHERITS_GRANTS_FROM, MODULES, SCREEN_MODELS


class PermissionSeeder(BaseSeeder):
    name = "PermissionSeeder"

    def _seed_mobile_app_catalog(self):
        """The App Module master, and the citizen app's own screens.

        Every other mobile screen is governed by the ordinary web permission it
        maps to (see app/utils/app_feature_grants.py), so only the citizen app
        needs rows of its own — its routes are middleware-exempt and
        self-scoped, leaving nothing in the normal catalog to grant.

        Kept under its own MainScreenType so it never appears in the web
        sidebar and is untouched by the megamenu deactivation pass above.
        """
        from app.models.superadmin.screen_management.app_module import AppModule
        from app.utils.app_feature_grants import (
            APP_MODULE_SEED,
            CITIZEN_APP_MAINSCREEN,
            CITIZEN_APP_SCREENS,
        )

        for entry in APP_MODULE_SEED:
            module, _ = AppModule.objects.get_or_create(
                module_key=entry["module_key"],
                defaults={
                    "surface_key": entry["surface_key"],
                    "label": entry["label"],
                    "route": entry["route"],
                    "order_no": entry["order_no"],
                    "description": entry["description"],
                },
            )
            # Never overwrite a label or ordering an admin changed in web; the
            # read-only identity fields are kept in step with the app build.
            changed = []
            if module.surface_key != entry["surface_key"]:
                module.surface_key = entry["surface_key"]
                changed.append("surface_key")
            if module.route != entry["route"]:
                module.route = entry["route"]
                changed.append("route")
            if module.is_deleted:
                module.is_deleted = False
                module.is_active = True
                changed += ["is_deleted", "is_active"]
            if changed:
                module.save(update_fields=changed + ["updated_at"])

        mobile_type, _ = MainScreenType.objects.get_or_create(
            type_name="mobile-app",
            defaults={"is_active": True, "is_deleted": False},
        )
        citizen_main, _ = self._get_or_create_main_screen(
            mobile_type,
            CITIZEN_APP_MAINSCREEN,
            1,
            CITIZEN_APP_MAINSCREEN,
            "Citizen app screens (mobile only)",
        )
        for index, screen_name in enumerate(CITIZEN_APP_SCREENS, start=1):
            self._get_or_create_user_screen(
                citizen_main,
                screen_name,
                index,
                screen_name,
                screen_name,
                screen_name.replace("app-citizen-", "Citizen ").title(),
            )

        self.log(
            f"Mobile app catalog: {AppModule.objects.filter(is_deleted=False).count()} "
            f"modules, {len(CITIZEN_APP_SCREENS)} citizen screens."
        )

    def _get_unique_value(self, model_class, field_name, preferred_value, exclude_pk=None):
        if not preferred_value:
            preferred_value = "screen"

        candidate = preferred_value
        counter = 2
        while model_class.objects.filter(**{field_name: candidate}).exclude(pk=exclude_pk).exists():
            candidate = f"{preferred_value}-{counter}"
            counter += 1

        return candidate

    def _get_or_create_main_screen(self, mainscreentype, name, order_no, icon_name, description):
        existing = MainScreen.objects.filter(mainscreen_name=name).first()
        icon_name = self._get_unique_value(
            MainScreen,
            "icon_name",
            icon_name,
            exclude_pk=existing.pk if existing else None,
        )

        return MainScreen.objects.update_or_create(
            mainscreen_name=name,
            defaults={
                "mainscreentype_id": getattr(mainscreentype, "pk", mainscreentype),
                "icon_name": icon_name,
                "order_no": order_no,
                "description": description,
                "is_active": True,
                "is_deleted": False,
            },
        )

    def _get_or_create_user_screen(
        self,
        main_screen,
        userscreen_name,
        order_no,
        folder_name,
        icon_name,
        description,
    ):
        model_app_label, model_name = SCREEN_MODELS.get(userscreen_name, (None, None))
        existing = UserScreen.objects.filter(userscreen_name=userscreen_name).first()
        folder_name = self._get_unique_value(
            UserScreen,
            "folder_name",
            folder_name,
            exclude_pk=existing.pk if existing else None,
        )
        icon_name = self._get_unique_value(
            UserScreen,
            "icon_name",
            icon_name,
            exclude_pk=existing.pk if existing else None,
        )

        main_id = getattr(main_screen, "pk", main_screen)
        result = UserScreen.objects.update_or_create(
            userscreen_name=userscreen_name,
            defaults={
                "mainscreen_id": main_id,
                "folder_name": folder_name,
                "icon_name": icon_name,
                "order_no": order_no,
                "description": description,
                "model_app_label": model_app_label,
                "model_name": model_name,
                "is_active": True,
                "is_deleted": False,
            },
        )
        if existing and existing.mainscreen_id != main_id:
            self._repoint_grants(existing.unique_id, main_id)
        return result

    def _repoint_grants(self, userscreen_id, main_id):
        """A screen moved to another module in the catalog: its grant rows
        carry their own mainscreen_id and the permission payload is keyed by
        it, so re-point them or every existing grant on it goes inert."""
        from app.models.superadmin.screen_management.userscreenpermission import (
            UserScreenPermission,
        )
        from app.models.superadmin.staff_management.staff_access_configuration import (
            StaffAccessConfigurationPermission,
        )

        moved = 0
        for model in (UserScreenPermission, StaffAccessConfigurationPermission):
            moved += model.objects.filter(userscreen_id=userscreen_id).exclude(
                mainscreen_id=main_id
            ).update(mainscreen_id=main_id)
        if moved:
            self.log(f"Re-pointed {moved} grants of moved screen {userscreen_id}.")

    def _move_mainscreen_orders_out_of_range(self, mainscreentype, reserved_count):
        screens = list(
            MainScreen.objects.filter(mainscreentype_id=mainscreentype)
            .order_by("order_no", "unique_id")
        )
        if not screens:
            return

        max_order = max((screen.order_no or 0) for screen in screens)
        offset = max_order + len(screens) + reserved_count + 1000
        for idx, screen in enumerate(screens, start=1):
            screen.order_no = offset + idx
            screen.save(update_fields=["order_no"])

    def _move_userscreen_orders_out_of_range(self, main_screen, reserved_count):
        screens = list(
            UserScreen.objects.filter(mainscreen_id=getattr(main_screen, "pk", main_screen))
            .order_by("order_no", "unique_id")
        )
        if not screens:
            return

        max_order = max((screen.order_no or 0) for screen in screens)
        offset = max_order + len(screens) + reserved_count + 1000
        for idx, screen in enumerate(screens, start=1):
            screen.order_no = offset + idx
            screen.save(update_fields=["order_no"])

    def _deactivate_removed_sidebar_screens(
        self,
        mainscreentype,
        active_modules,
        active_user_screens,
    ):
        stale_user_screens = UserScreen.objects.filter(
            mainscreen_id__in=MainScreen.objects.filter(mainscreentype_id=mainscreentype).values("unique_id"),
        ).exclude(userscreen_name__in=active_user_screens)
        stale_userscreen_count = stale_user_screens.update(is_active=False, is_deleted=True)

        stale_main_screens = MainScreen.objects.filter(
            mainscreentype_id=mainscreentype,
        ).exclude(mainscreen_name__in=active_modules)
        stale_mainscreen_count = stale_main_screens.update(is_active=False, is_deleted=True)

        if stale_mainscreen_count or stale_userscreen_count:
            self.log(
                "Soft-disabled "
                f"{stale_mainscreen_count} stale main screens and "
                f"{stale_userscreen_count} stale user screens not present in AppSidebar."
            )

    # Screens whose feature was removed; hidden on every seed run.
    RETIRED_USER_SCREENS = ("teams",)

    @staticmethod
    def _grant_models():
        from app.models.superadmin.screen_management.userscreenpermission import (
            UserScreenPermission,
        )
        from app.models.superadmin.staff_management.staff_access_configuration import (
            StaffAccessConfigurationPermission,
        )

        return (UserScreenPermission, StaffAccessConfigurationPermission)

    @staticmethod
    def _rename_row(model, field, name, legacy):
        """Rename the row still carrying a legacy (or differently-cased) name.

        Grants point at the row's unique_id, so renaming in place keeps them.
        Compared in Python: MySQL's collation is case-insensitive, so the
        database alone would call "Dashboard" and "dashboard" the same name.
        """
        rows = list(model.objects.filter(**{f"{field}__in": (name, *legacy)}))
        if any(getattr(row, field) == name for row in rows):
            return False
        rank = {old.lower(): index for index, old in enumerate((name, *legacy))}
        rows.sort(key=lambda row: (row.is_deleted, rank.get(getattr(row, field).lower(), 99)))
        if not rows:
            return False
        setattr(rows[0], field, name)
        rows[0].save(update_fields=[field])
        return True

    def _rename_legacy_rows(self):
        renamed = 0
        for name, mod in MODULES.items():
            renamed += self._rename_row(MainScreen, "mainscreen_name", name, mod["legacy"])
            for scr in mod["screens"]:
                renamed += self._rename_row(
                    UserScreen, "userscreen_name", scr["name"], scr["legacy"]
                )
        if renamed:
            self.log(f"Renamed {renamed} main/user screens to their sidebar names.")

    def _copy_grants(self, source_ids, target, *, move):
        """Copy the grants on `source_ids` onto `target`, skipping duplicates.

        With `move`, the source grants are soft-deleted afterwards, so a later
        seed run cannot copy them back over a grant an admin has since revoked.
        """
        copied = 0
        for model in self._grant_models():
            skip = {"unique_id", "created_at", "updated_at", "created_by", "updated_by",
                    "order_no", "description"}
            fields = [f.name for f in model._meta.concrete_fields if f.name not in skip]
            sources = model.objects.filter(userscreen_id__in=source_ids, is_deleted=False)
            for row in sources:
                values = {field: getattr(row, field) for field in fields}
                values["userscreen_id"] = target.unique_id
                values["mainscreen_id"] = target.mainscreen_id
                if model.objects.filter(**values).exists():
                    continue
                extra = {"order_no": row.order_no}
                if hasattr(row, "description"):
                    extra["description"] = row.description
                model.objects.create(**values, **extra)
                copied += 1
            if move:
                sources.update(is_deleted=True, is_active=False)
        return copied

    def _merge_folded_screens(self, user_screens):
        """Give each screen the grants of the screens folded into it.

        Its `absorbs` list (tabs that became one page), plus any leftover row
        still carrying one of its legacy names.
        """
        for mod in MODULES.values():
            for scr in mod["screens"]:
                target = user_screens.get(scr["name"])
                names = (*scr["legacy"], *scr["absorbs"])
                if not target or not names:
                    continue
                source_ids = [
                    row.unique_id
                    for row in UserScreen.objects.filter(userscreen_name__in=names)
                    if row.userscreen_name in names and row.pk != target.pk
                ]
                if source_ids and (copied := self._copy_grants(source_ids, target, move=True)):
                    self.log(f"{scr['name']}: moved {copied} grants from {', '.join(names)}.")

    def _inherit_grants(self, screen, source_name):
        """A NEW screen split from an existing one starts with its grants, so
        nobody loses access (catalog `inherits_grants_from`)."""
        source = UserScreen.objects.filter(
            userscreen_name=source_name, is_deleted=False
        ).first()
        if source and (copied := self._copy_grants([source.unique_id], screen, move=False)):
            self.log(f"{screen.userscreen_name}: copied {copied} grants from {source_name}.")

    def run(self):
        UserScreen.objects.filter(userscreen_name__in=self.RETIRED_USER_SCREENS).update(
            is_active=False, is_deleted=True
        )

        for action_name in ("view", "export"):
            UserScreenAction.objects.update_or_create(
                action_name=action_name,
                defaults={
                    "variable_name": action_name,
                    "is_active": True,
                    "is_deleted": False,
                },
            )

        megamenu, _ = MainScreenType.objects.get_or_create(
            type_name="megamenu",
            defaults={
                "is_active": True,
                "is_deleted": False,
            },
        )

        self._rename_legacy_rows()

        # Modules and screens come from the one permission catalog
        # (app/utils/permission_catalog.py), which mirrors the sidebar.
        # Add or rename screens there, never here.
        sidebar_modules = [
            {
                "module": name,
                "icon": mod["icon"],
                "order": order,
                "description": mod["description"],
                "subitems": [
                    (scr["name"], scr["name"], scr["name"], index, scr["label"])
                    for index, scr in enumerate(mod["screens"], start=1)
                ],
            }
            for order, (name, mod) in enumerate(MODULES.items(), start=1)
        ]

        self._move_mainscreen_orders_out_of_range(megamenu.pk, len(sidebar_modules))

        main_screens = {}
        user_screens = {}
        created_main_screens = 0
        created_user_screens = 0
        active_modules = {section["module"] for section in sidebar_modules}
        active_user_screens = {
            subitem[0]
            for section in sidebar_modules
            for subitem in section.get("subitems", [])
        }

        for section in sidebar_modules:
            main_screen, created = self._get_or_create_main_screen(
                megamenu.pk,
                section["module"],
                section["order"],
                section["icon"],
                section["description"],
            )
            main_screens[section["module"]] = main_screen
            if created:
                created_main_screens += 1

            self._move_userscreen_orders_out_of_range(main_screen, len(section.get("subitems", [])))

            for index, subitem in enumerate(section.get("subitems", []), start=1):
                userscreen_name, folder_name, icon_name, order_no, description = subitem
                user_screen, created = self._get_or_create_user_screen(
                    main_screen,
                    userscreen_name,
                    order_no or index,
                    folder_name,
                    icon_name,
                    description,
                )
                user_screens[userscreen_name] = user_screen
                if created:
                    created_user_screens += 1
                    if userscreen_name in INHERITS_GRANTS_FROM:
                        self._inherit_grants(user_screen, INHERITS_GRANTS_FROM[userscreen_name])

        self._merge_folded_screens(user_screens)

        self._seed_mobile_app_catalog()

        self._deactivate_removed_sidebar_screens(
            megamenu.pk,
            active_modules,
            active_user_screens,
        )

        self.log(
            f"Sidebar-based permission screens seeded: {created_main_screens} main screens and {created_user_screens} user screens."
        )

import re
import importlib
import inspect
import pkgutil

from django.apps import apps


SYSTEM_FIELDS = {"id", "pk"}


def normalize_model_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def model_key_variants(value):
    key = normalize_model_key(value)
    if not key:
        return set()

    variants = {key}
    if key.endswith("ies") and len(key) > 3:
        variants.add(f"{key[:-3]}y")
    if key.endswith("s") and len(key) > 1:
        variants.add(key[:-1])

    expanded = set(variants)
    for item in variants:
        for suffix in ("creations", "creation", "details", "detail", "logs", "log"):
            if item.endswith(suffix) and len(item) > len(suffix):
                expanded.add(item[: -len(suffix)])

    return expanded


def get_model_aliases(model_class):
    aliases = set()
    for value in (
        model_class.__name__,
        model_class._meta.model_name,
        model_class._meta.verbose_name,
        model_class._meta.verbose_name_plural,
        model_class._meta.db_table,
    ):
        aliases.update(model_key_variants(value))
    return aliases


def _model_from_viewset(viewset_class):
    serializer_class = getattr(viewset_class, "serializer_class", None)
    serializer_meta = getattr(serializer_class, "Meta", None)
    model_class = getattr(serializer_meta, "model", None)
    if model_class:
        return model_class

    queryset = getattr(viewset_class, "queryset", None)
    return getattr(queryset, "model", None)


def iter_viewset_model_mappings():
    try:
        import app.viewsets as viewsets_package
    except Exception:
        return

    for module_info in pkgutil.walk_packages(
        viewsets_package.__path__,
        prefix=f"{viewsets_package.__name__}.",
    ):
        if module_info.ispkg:
            continue
        try:
            module = importlib.import_module(module_info.name)
        except Exception:
            continue

        for _, viewset_class in inspect.getmembers(module, inspect.isclass):
            model_class = _model_from_viewset(viewset_class)
            if not model_class:
                continue

            aliases = get_model_aliases(model_class)
            aliases.update(model_key_variants(viewset_class.__name__))
            aliases.update(model_key_variants(getattr(viewset_class, "permission_resource", "")))
            yield aliases, model_class


def resolve_userscreen_model(userscreen):
    """
    Resolve a UserScreen to a Django model through the app registry.

    The legacy model_app_label/model_name columns are still honored when they
    are already populated, but new code does not require hardcoded mappings.
    """
    model_app_label = getattr(userscreen, "model_app_label", None)
    model_name = getattr(userscreen, "model_name", None)

    if model_app_label and model_name:
        try:
            return apps.get_model(model_app_label, model_name)
        except LookupError:
            pass

    candidates = set()
    candidates.update(model_key_variants(getattr(userscreen, "userscreen_name", "")))
    candidates.update(model_key_variants(getattr(userscreen, "folder_name", "")))

    for model_class in apps.get_models():
        if candidates.intersection(get_model_aliases(model_class)):
            return model_class

    for aliases, model_class in iter_viewset_model_mappings():
        if candidates.intersection(aliases):
            return model_class

    return None


def iter_model_columns(model_class):
    for field in model_class._meta.get_fields():
        if field.auto_created and not field.concrete:
            continue
        if not getattr(field, "concrete", False):
            continue
        if field.name in SYSTEM_FIELDS:
            continue
        yield field

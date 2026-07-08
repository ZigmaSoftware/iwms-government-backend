"""
Registry of masters that can be attached to a hierarchy node.

This is the single place to declare "which masters are assignable". Adding a
new assignable master = one entry here. Nothing else changes: the generic
HierarchyAssignment API and the frontend "Assign Hierarchy" form read this
registry to build their dropdowns.

Each entry maps a stable ``entity_type`` key to:
    model      : the Django model class
    label      : human label shown in the UI
    pk_field   : the model's primary-key field name (its unique_id field)
    name_attr  : attribute / dotted path used to display each record
    queryset   : optional callable returning the base queryset (defaults to
                 active, non-deleted rows)
"""

from importlib import import_module


def _attr(obj, dotted):
    """Resolve a possibly-dotted attribute path, returning '' on any miss."""
    cur = obj
    for part in dotted.split("."):
        cur = getattr(cur, part, None)
        if cur is None:
            return ""
    return str(cur)


# entity_type -> config. Models are referenced lazily by import path so this
# module stays import-safe even if a model is being migrated.
ASSIGNABLE_ENTITIES = {
    "department": {
        "label": "Department",
        "model_path": "app.models.masters.department.Department",
        "pk_field": "unique_id",
        "name_attr": "department_name",
    },
    "designation": {
        "label": "Designation",
        "model_path": "app.models.masters.designation.Designation",
        "pk_field": "unique_id",
        "name_attr": "designation_name",
    },
    "customer": {
        "label": "Customer",
        "model_path": "app.models.customers.customercreation.CustomerCreation",
        "pk_field": "unique_id",
        "name_attr": "customer_name",
    },
    "staff": {
        "label": "Staff",
        "model_path": "app.models.user_creations.staffcreation.StaffcreationOfficeDetails",
        "pk_field": "staff_unique_id",
        "name_attr": "employee_name",
    },
    "panchayat_leader": {
        "label": "Panchayat Leader",
        "model_path": "app.models.masters.panchayat_leader_login.PanchayatLeaderLogin",
        "pk_field": "unique_id",
        "name_attr": "leader_name",
    },
    "district_leader": {
        "label": "District Leader",
        "model_path": "app.models.masters.district_leader_login.DistrictLeaderLogin",
        "pk_field": "unique_id",
        "name_attr": "leader_name",
    },
    "bin": {
        "label": "Bin",
        "model_path": "app.models.assets.bins.Bins",
        "pk_field": "unique_id",
        "name_attr": "bin_name",
    },
    "collection_point": {
        "label": "Collection Point",
        "model_path": "app.models.schedule_masters.collection_point.Collection_point",
        "pk_field": "unique_id",
        "name_attr": "cp_name",
    },
}


def _load_model(model_path):
    module_path, cls_name = model_path.rsplit(".", 1)
    return getattr(import_module(module_path), cls_name)


def get_entity_config(entity_type):
    cfg = ASSIGNABLE_ENTITIES.get(entity_type)
    if not cfg:
        return None
    return cfg


def resolve_entity_model(entity_type):
    cfg = get_entity_config(entity_type)
    if not cfg:
        return None
    return _load_model(cfg["model_path"])


def list_entity_types():
    """Lightweight list of {key, label} for building dropdowns."""
    return [
        {"key": key, "label": cfg["label"]}
        for key, cfg in ASSIGNABLE_ENTITIES.items()
    ]


def list_entity_records(entity_type):
    """Return [{id, label}] of selectable records for one master type."""
    cfg = get_entity_config(entity_type)
    if not cfg:
        return []
    model = _load_model(cfg["model_path"])

    qs = model.objects.all()
    # Most masters use BaseMaster soft-delete flags; filter when present.
    field_names = {f.name for f in model._meta.get_fields()}
    if "is_deleted" in field_names:
        qs = qs.filter(is_deleted=False)

    pk_field = cfg["pk_field"]
    name_attr = cfg["name_attr"]
    records = []
    for obj in qs[:1000]:
        records.append(
            {
                "id": str(getattr(obj, pk_field)),
                "label": _attr(obj, name_attr) or str(getattr(obj, pk_field)),
            }
        )
    return records


def entity_label(entity_type, entity_id):
    """Best-effort human label for one record (cached on the assignment)."""
    cfg = get_entity_config(entity_type)
    if not cfg:
        return None
    model = _load_model(cfg["model_path"])
    obj = model.objects.filter(**{cfg["pk_field"]: entity_id}).first()
    if not obj:
        return None
    return _attr(obj, cfg["name_attr"]) or str(entity_id)

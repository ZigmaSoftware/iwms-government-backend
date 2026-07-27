"""
Shared helpers for seeders operating on the two distinct scoping levels
this project's data now spans:

  - LOCAL BODY level (Corporation, Municipality, Town Panchayat, Panchayat
    Union, each Panchayat) — where VehicleCreation and StaffTemplate /
    AlternativeStaffTemplate live. A local body owns a pool of vehicles and
    driver/operator crews sized to its own ward count (2 per ward: one for
    the bin route, one for the household route).
  - WARD level (every Ward under any of the 5 local body types) — where
    TripPlan, Collection_point, BinCollectionEvent and household collection
    ultimately operate. Each ward's trip plan draws ONE vehicle and ONE
    staff template from its parent local body's pool — never reused by any
    other ward's trip plan.

masters/ward.py::WardSeeder is the single source of truth for how many
wards each local body type gets; everything here mirrors that count so a
local body's vehicle/template pool always exactly matches its own ward
count x 2 collection types.
"""

from app.management.commands.seeders.tn_geo_data import DISTRICTS
from app.models.masters.corporation import Corporation
from app.models.masters.municipality import Municipality
from app.models.masters.panchayat import Panchayat
from app.models.masters.panchayat_union import PanchayatUnion
from app.models.masters.town_panchayat import TownPanchayat
from app.models.masters.ward import Ward

# Wards per local body — kept deliberately small (each ward fans out into a
# trip plan x 2 collection types x HISTORY_DAYS of daily assignments, so
# ward count is the single biggest lever on total seed volume/runtime). 1
# ward per local body x 21 local bodies (3 districts x [Corporation +
# Municipality + Town Panchayat + Panchayat Union] + 9 Panchayats total)
# = 21 wards = 42 trip plans (2 per ward) — the closest clean, uniform
# split to a ~40 trip-plan target while still giving every local body type
# real ward-level presence.
WARDS_PER_LOCAL_BODY = {
    "corporation": 1,
    "municipality": 1,
    "town_panchayat": 1,
    "panchayat_union": 1,
    "panchayat": 1,
}

FLAT_GEO_FIELDS = (
    "state", "district", "area_type", "corporation",
    "municipality", "town_panchayat", "panchayat_union", "panchayat",
)


# Local bodies of different types sometimes share the same root locality
# name (e.g. Erode's "Bhavani Municipality" and "Bhavani Panchayat" both
# strip down to "Bhavani") — tag every generated ward name with its local
# body type so two genuinely different Ward rows never end up with the
# same display name, no matter which pair of types collides.
_WARD_NAME_TAG_BY_TYPE = {
    "corporation": " (Corp)",
    "municipality": " (M)",
    "town_panchayat": " (TP)",
    "panchayat_union": " (PU)",
    "panchayat": " (P)",
}


def ward_type_tag(parent_type):
    return _WARD_NAME_TAG_BY_TYPE.get(parent_type, "")


def local_body_ward_name(local_body_name, index, parent_type=None):
    short = (
        local_body_name
        .replace(" Corporation", "").replace(" Municipality", "")
        .replace(" Town Panchayat", "").replace(" Panchayat Union", "")
        .replace(" Panchayat", "")
    )
    tag = _WARD_NAME_TAG_BY_TYPE.get(parent_type, "")
    return f"{short}{tag} Ward {index}"


_NAME_ATTR_BY_TYPE = {
    "corporation": "corporation_name",
    "municipality": "municipality_name",
    "town_panchayat": "town_panchayat_name",
    "panchayat_union": "union_name",
    "panchayat": "panchayat_name",
}


def local_body_name(parent_type, parent):
    if not parent:
        return None
    return getattr(parent, _NAME_ATTR_BY_TYPE[parent_type])


def local_bodies_for_district(district_name):
    """[{"parent_type", "parent", "ward_count"}, ...] — every local body in
    the district: the Corporation, Municipality, TownPanchayat,
    PanchayatUnion, and each named Panchayat."""
    geo = DISTRICTS[district_name]
    result = []

    corporation = Corporation.objects.filter(
        corporation_name=geo["corporation_name"], is_deleted=False
    ).first()
    if corporation:
        result.append({
            "parent_type": "corporation", "parent": corporation,
            "ward_count": WARDS_PER_LOCAL_BODY["corporation"],
        })

    municipality = Municipality.objects.filter(district_id__name=district_name, is_deleted=False).first()
    if municipality:
        result.append({
            "parent_type": "municipality", "parent": municipality,
            "ward_count": WARDS_PER_LOCAL_BODY["municipality"],
        })

    town_panchayat = TownPanchayat.objects.filter(district_id__name=district_name, is_deleted=False).first()
    if town_panchayat:
        result.append({
            "parent_type": "town_panchayat", "parent": town_panchayat,
            "ward_count": WARDS_PER_LOCAL_BODY["town_panchayat"],
        })

    panchayat_union = PanchayatUnion.objects.filter(district_id__name=district_name, is_deleted=False).first()
    if panchayat_union:
        result.append({
            "parent_type": "panchayat_union", "parent": panchayat_union,
            "ward_count": WARDS_PER_LOCAL_BODY["panchayat_union"],
        })

    for panchayat_name, _lat, _lon, _pincode in geo["panchayats"]:
        panchayat = Panchayat.objects.filter(panchayat_name=panchayat_name, is_deleted=False).first()
        if panchayat:
            result.append({
                "parent_type": "panchayat", "parent": panchayat,
                "ward_count": WARDS_PER_LOCAL_BODY["panchayat"],
            })

    return result


def geo_defaults_for_local_body(parent_type, parent, include_country=False):
    """Flat-geo {field: value} dict pointing a model at this exact local
    body (state/district/area_type inherited from the local body itself,
    plus the local body's own FK set, every other local-body FK cleared).
    Pass include_country=True for models (VehicleCreation, Collection_point,
    Bins) that also carry a `country` FK alongside the usual block."""
    values = {field: None for field in FLAT_GEO_FIELDS}
    values["state"] = parent.state_id
    values["district"] = parent.district_id
    values["area_type"] = parent.area_type_id
    values[parent_type] = parent
    if include_country:
        values["country"] = parent.district_id.country_id if parent.district_id else None
    return values


def wards_for_local_body(parent_type, parent):
    """Every seeded Ward under this specific local body, in the same
    deterministic order WardSeeder created them in (corporation wards keep
    their curated name order; generated wards are Ward N, N=1..count)."""
    filter_kwargs = {parent_type: parent, "is_deleted": False}
    wards = {w.ward_name: w for w in Ward.objects.filter(**filter_kwargs)}

    if parent_type == "corporation":
        geo = DISTRICTS[parent.district_id.name]
        ordered_names = [
            f"{name}{ward_type_tag('corporation')}" for name, _lat, _lon
            in geo["corporation_wards"][:WARDS_PER_LOCAL_BODY["corporation"]]
        ]
    else:
        name = local_body_name(parent_type, parent)
        count = WARDS_PER_LOCAL_BODY[parent_type]
        ordered_names = [local_body_ward_name(name, i, parent_type) for i in range(1, count + 1)]

    return [wards[name] for name in ordered_names if name in wards]


def wards_for_district(district_name):
    """[{"ward", "parent_type", "parent"}, ...] across every local body in
    the district, ordered local-body-by-local-body."""
    result = []
    for lb in local_bodies_for_district(district_name):
        for ward in wards_for_local_body(lb["parent_type"], lb["parent"]):
            result.append({"ward": ward, "parent_type": lb["parent_type"], "parent": lb["parent"]})
    return result

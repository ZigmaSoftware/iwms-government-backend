"""
Every Tamil Nadu district and local body — 38 districts, Corporations,
Municipalities, Town Panchayats, Panchayat Unions and Village Panchayats —
with real boundary polygons, read from data/tn_local_bodies.json.gz.

The data file is generated offline by data/build_tn_local_bodies.py from
the Local Government Directory (LGD) and official LGD/SBM boundary layers;
see that script for sources and how boundaries are resolved. This module
only reads it and applies the seeders' naming conventions, so the rows the
seeders write match names the rest of the seed data already uses
("Erode Corporation", "Bhavani Municipality", "Anthiyur Panchayat Union").
"""

import gzip
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "tn_local_bodies.json.gz"

# Short codes stored in District.district_code (the first five predate this
# file and are kept unchanged).
DISTRICT_CODES = {
    "Ariyalur": "ARY", "Chengalpattu": "CGL", "Chennai": "CHN", "Coimbatore": "CBE",
    "Cuddalore": "CDL", "Dharmapuri": "DPI", "Dindigul": "DGL", "Erode": "ERD",
    "Kallakurichi": "KKI", "Kancheepuram": "KPM", "Kanniyakumari": "KKM", "Karur": "KRR",
    "Krishnagiri": "KGI", "Madurai": "MDU", "Mayiladuthurai": "MYD", "Nagapattinam": "NGP",
    "Namakkal": "NMK", "Perambalur": "PMB", "Pudukkottai": "PDK", "Ramanathapuram": "RMD",
    "Ranipet": "RPT", "Salem": "SLM", "Sivaganga": "SVG", "Tenkasi": "TKS",
    "Thanjavur": "TNJ", "The Nilgiris": "NLG", "Theni": "THN", "Thiruvallur": "TVL",
    "Thiruvarur": "TVR", "Thoothukkudi": "TUT", "Tiruchirappalli": "TRY", "Tirunelveli": "TEN",
    "Tirupathur": "TPT", "Tiruppur": "TUP", "Tiruvannamalai": "TVM", "Vellore": "VLR",
    "Viluppuram": "VPM", "Virudhunagar": "VNR",
}


@lru_cache(maxsize=1)
def load():
    with gzip.open(DATA_FILE, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def as_coordinates(points):
    """[[lat, lon], ...] from the data file -> the models' coordinates format."""
    return [{"latitude": lat, "longitude": lon} for lat, lon in points]


def district_names():
    """{district LGD code: district name}"""
    return {d["lgd"]: d["name"] for d in load()["districts"]}


def districts():
    """[{"name", "code", "coordinates"}, ...] for all 38 districts."""
    return [
        {
            "name": d["name"],
            "code": DISTRICT_CODES.get(d["name"], d["name"][:3].upper()),
            "coordinates": as_coordinates(d["coordinates"]),
        }
        for d in load()["districts"]
    ]


def _suffixed(name, suffix):
    return name if name.lower().endswith(suffix.lower()) else f"{name} {suffix}"


def _local_bodies(key, suffix):
    names = district_names()
    return [
        {
            "district": names[lb["district"]],
            "name": _suffixed(lb["name"], suffix),
            "coordinates": as_coordinates(lb["coordinates"]),
        }
        for lb in load()[key]
    ]


def corporations():
    return _local_bodies("corporations", "Corporation")


def municipalities():
    return _local_bodies("municipalities", "Municipality")


def town_panchayats():
    return _local_bodies("town_panchayats", "Town Panchayat")


def panchayat_unions():
    return _local_bodies("panchayat_unions", "Panchayat Union")


def panchayats():
    """Village panchayats as "<Name> Panchayat". Names repeat across a
    district (e.g. two "Pudur"s in different unions), and the seeders key
    rows on (district, name), so a repeated name gets its union appended —
    "Pudur Panchayat (Anthiyur)" — and the LGD code if it still repeats."""
    data = load()
    names = district_names()
    union_names = {u["lgd"]: u["name"] for u in data["panchayat_unions"]}

    base = [(vp, f"{vp['name']} Panchayat") for vp in data["panchayats"]]
    per_district = Counter((vp["district"], name) for vp, name in base)
    with_union = [
        (vp, name if per_district[vp["district"], name] == 1 else f"{name} ({union_names[vp['union']]})")
        for vp, name in base
    ]
    per_district = Counter((vp["district"], name) for vp, name in with_union)

    result = []
    for vp, name in with_union:
        if per_district[vp["district"], name] > 1:
            name = f"{name} [{vp['lgd']}]"
        result.append({
            "district": names[vp["district"]],
            "name": name,
            "coordinates": as_coordinates(vp["coordinates"]),
        })
    return result

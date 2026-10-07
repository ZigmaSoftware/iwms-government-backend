"""
Builds tn_local_bodies.json.gz — every Tamil Nadu district and local body
(Corporation, Municipality, Town Panchayat, Panchayat Union, Village
Panchayat) with a real boundary polygon, consumed by the masters seeders.

This is an offline, one-time data-prep script, NOT part of `manage.py seed`
(its dependencies are not backend requirements). Re-run it only to refresh
the data file:

    uv run --no-project --with duckdb --with shapely --with py7zr \
        python app/management/commands/seeders/data/build_tn_local_bodies.py \
        --cache /tmp/tn_geo_cache

Sources (all official Government of India data, re-published by
github.com/ramSeraph/indian_admin_boundaries and github.com/ramSeraph/opendata):
  - Names / types / hierarchy: Local Government Directory (LGD) daily
    snapshots — districts, urban_local_bodies, pri_local_bodies,
    statewise_ulbs_coverage.
  - Boundaries: LGD_Districts, LGD_Blocks, LGD_panchayats (GP + census-town
    polygons), LGD_Villages and Swachh Bharat Mission SBM_ULBs; Census 2011
    village points as the last-resort location.

Boundary fallbacks, in order, when a body has no polygon of its own:
  ULB:   SBM polygon (by census-2011 code) -> census-town polygon in the
         panchayat layer -> union of the LGD villages it covers -> a single
         census village point -> same-named village in its district.
  Union: LGD block polygon (by block-panchayat code) -> union of its VPs
         -> same-named village in its district.
  VP:    GP polygon (by LGD code) -> union of its LGD villages -> a single
         census village point -> same-named village in its district.
A single point is drawn as a pin by the maps rather than an invented shape;
anything still unresolved gets an empty list.
"""

import argparse
import csv
import datetime
import gzip
import io
import json
import os
import re
import urllib.request
from collections import defaultdict

import duckdb
import py7zr
from shapely import wkb
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

STATE_LGD = 33
BOUNDARIES = "https://github.com/ramSeraph/indian_admin_boundaries/releases/download"
LGD_RELEASE_API = "https://api.github.com/repos/ramSeraph/opendata/releases/tags/{tag}"
LGD_TABLES = ("districts", "urban_local_bodies", "pri_local_bodies", "statewise_ulbs_coverage", "gp_mapping")

LAYERS = {
    "districts": f"SELECT * EXCLUDE(bbox) FROM '{BOUNDARIES}/districts/LGD_Districts.parquet' WHERE state_lgd={STATE_LGD}",
    "blocks": f"SELECT * EXCLUDE(bbox) FROM '{BOUNDARIES}/blocks/LGD_Blocks.parquet' WHERE state_lgd={STATE_LGD}",
    "panchayats": f"SELECT * EXCLUDE(bbox) FROM '{BOUNDARIES}/panchayats/LGD_panchayats.parquet' WHERE st_lgd={STATE_LGD}",
    "ulbs": f"SELECT * EXCLUDE(bbox) FROM '{BOUNDARIES}/urban/SBM_ULBs.parquet' WHERE stcode='{STATE_LGD}'",
    "villages": f"SELECT * EXCLUDE(bbox) FROM '{BOUNDARIES}/villages/LGD_Villages.parquet' WHERE state_lgd={STATE_LGD}",
    "village_points": (
        f"SELECT vilcode11, GP_CODE, Lat, Long FROM '{BOUNDARIES}/census-2011/Census_Villages.parquet' "
        f"WHERE ST_LGD={STATE_LGD} AND Lat IS NOT NULL"
    ),
}

# District Panchayat names in LGD that are spelled differently from the
# district itself.
DISTRICT_ALIASES = {
    "sivagangai": "Sivaganga",
    "tiruvallur": "Thiruvallur",
    "tiruvarur": "Thiruvarur",
    "villupuram": "Viluppuram",
}

# Max polygon vertices kept per body type (adaptive simplification).
MAX_POINTS = {
    "district": 400,
    "corporation": 200,
    "municipality": 120,
    "town_panchayat": 80,
    "panchayat_union": 160,
    "panchayat": 50,
}

ULB_TYPES = {"4": "corporation", "5": "municipality", "7": "town_panchayat"}


# ---------------------------------------------------------------- download

def fetch_layers(cache):
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    for name, query in LAYERS.items():
        path = os.path.join(cache, f"{name}.parquet")
        if not os.path.exists(path):
            print(f"downloading boundary layer {name} (slow for panchayats)...")
            con.execute(f"COPY ({query}) TO '{path}' (FORMAT parquet)")


def fetch_lgd(cache):
    latest = {}
    for tag in ("lgd-latest", "lgd-latest-extra1"):
        with urllib.request.urlopen(LGD_RELEASE_API.format(tag=tag)) as resp:
            for asset in json.load(resp)["assets"]:
                m = re.match(r"(.*?)\.(\d\d\w{3}\d{4})\.csv\.7z$", asset["name"])
                if not m or m.group(1) not in LGD_TABLES:
                    continue
                when = datetime.datetime.strptime(m.group(2), "%d%b%Y")
                if m.group(1) not in latest or when > latest[m.group(1)][0]:
                    latest[m.group(1)] = (when, asset["browser_download_url"])

    paths = {}
    for table, (when, url) in latest.items():
        path = os.path.join(cache, f"{table}.csv")
        if not os.path.exists(path):
            print(f"downloading LGD {table} ({when:%d %b %Y})...")
            with urllib.request.urlopen(url) as resp:
                archive = py7zr.SevenZipFile(io.BytesIO(resp.read()))
            (name, data), = archive.readall().items()
            with open(path, "wb") as fh:
                fh.write(data.read())
        paths[table] = path
    return paths, {t: w.strftime("%Y-%m-%d") for t, (w, _) in latest.items()}


def read_csv(path, state_filter=True):
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            state = row.get("State Code") or row.get("State Name (In English)") or row.get("State Name")
            if not state_filter or state in (str(STATE_LGD), "Tamil Nadu"):
                yield row


# ---------------------------------------------------------------- geometry

def load_geoms(con, cache, layer, key_sql, where="TRUE"):
    """{key: [shapely geometry, ...]} for one cached boundary layer."""
    rows = con.execute(
        f"SELECT {key_sql}, ST_AsWKB(geometry) FROM '{cache}/{layer}.parquet' WHERE {where}"
    ).fetchall()
    out = defaultdict(list)
    for key, blob in rows:
        if blob is not None:
            out[str(key)].append(wkb.loads(bytes(blob)))
    return out


def dissolve(geoms):
    geoms = [g.buffer(0) for g in geoms if g is not None and not g.is_empty]
    return unary_union(geoms) if geoms else None


def largest_ring(geom):
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, MultiPolygon):
        geom = max(geom.geoms, key=lambda g: g.area)
    if not isinstance(geom, Polygon):
        geom = geom.convex_hull if geom.area else None
    return Polygon(geom.exterior) if geom is not None else None


def to_points(geom, max_points):
    """Largest outer ring, simplified until it fits max_points, as
    [[lat, lon], ...] rounded to 5 dp (~1 m) — closed (first == last)."""
    poly = largest_ring(geom)
    if poly is None:
        return []
    tolerance = 0.00005
    simple = poly
    while len(simple.exterior.coords) > max_points:
        simple = poly.simplify(tolerance, preserve_topology=True)
        tolerance *= 1.5
    return [[round(y, 5), round(x, 5)] for x, y in simple.exterior.coords]


def load_villages_by_name(con, cache):
    """{(district LGD code, name key): geometry} — for bodies created after
    2011 that no layer has by code, but which share a village's name."""
    rows = con.execute(
        f"SELECT dist_lgd, vilname11, vilnam_soi, ST_AsWKB(geometry) FROM '{cache}/villages.parquet'"
    ).fetchall()
    out = defaultdict(list)
    for district, name11, name_soi, blob in rows:
        if blob is None:
            continue
        geom = wkb.loads(bytes(blob))
        for name in {key(name11), key(name_soi)} - {""}:
            out[str(district), name].append(geom)
    return out


def load_points(con, cache, key_sql):
    """{key: [lat, lon]} from the census village points layer."""
    rows = con.execute(
        f"SELECT {key_sql}, Lat, Long FROM '{cache}/village_points.parquet' WHERE {key_sql} IS NOT NULL"
    ).fetchall()
    return {str(k): [round(lat, 5), round(lon, 5)] for k, lat, lon in rows}


# ---------------------------------------------------------------- naming

def clean(name):
    name = re.sub(r"\s+", " ", (name or "").strip())
    name = re.sub(r"\s*\(\s*", " (", name).replace(" )", ")")
    return name


def key(name):
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


# ---------------------------------------------------------------- build

def build(cache, out_path):
    os.makedirs(cache, exist_ok=True)
    fetch_layers(cache)
    lgd, lgd_dates = fetch_lgd(cache)

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")

    district_geoms = load_geoms(con, cache, "districts", "dist_lgd")
    block_geoms = load_geoms(con, cache, "blocks", "b_pan_code")
    gp_geoms = load_geoms(con, cache, "panchayats", "gpcode", "gpcode <> ''")
    town_geoms = load_geoms(con, cache, "panchayats", "vilcode11", "gpcode = '' AND vilcode11 <> 0")
    village_geoms = load_geoms(con, cache, "villages", "vil_lgd")
    sbm_geoms = load_geoms(con, cache, "ulbs", "ulbcode")
    point_by_village = load_points(con, cache, "vilcode11")
    point_by_gp = load_points(con, cache, "GP_CODE")
    villages_by_name = load_villages_by_name(con, cache)

    def same_named_village(district, name):
        geom = dissolve(villages_by_name.get((str(district), key(name)), []))
        return geom, ("name_match" if geom else None)

    stats = defaultdict(lambda: defaultdict(int))

    # -- districts
    districts = {}
    for row in read_csv(lgd["districts"]):
        code = row["District Code"]
        geom = dissolve(district_geoms.get(code, []))
        districts[code] = {
            "lgd": int(code),
            "name": clean(row["District Name(In English)"]),
            "coordinates": to_points(geom, MAX_POINTS["district"]),
        }
        stats["district"]["polygon" if geom else "none"] += 1
    district_by_key = {key(d["name"]): code for code, d in districts.items()}
    for alias, name in DISTRICT_ALIASES.items():
        district_by_key[alias] = district_by_key[key(name)]

    # -- ULBs (district + covered villages come from the coverage table)
    coverage = defaultdict(lambda: {"district": None, "villages": set()})
    for row in read_csv(lgd["statewise_ulbs_coverage"]):
        cov = coverage[row["Local Body Code"]]
        if row["District Code"] not in ("", "0"):
            cov["district"] = row["District Code"]
        if row["Village Code"] not in ("", "0"):
            cov["villages"].add(row["Village Code"])

    # LGD village code -> census 2011 code (key of the village points layer)
    census_of_village = {}
    gp_villages = defaultdict(set)
    for row in read_csv(lgd["gp_mapping"]):
        census_of_village[row["Village Code"]] = row["Village Census 2011 Code"]
        if row["Local Body Code"] not in ("", "0"):
            gp_villages[row["Local Body Code"]].add(row["Village Code"])

    def village_point(village_codes):
        for code in sorted(village_codes):
            point = point_by_village.get(census_of_village.get(code, ""))
            if point:
                return point
        return None

    ulbs = {t: [] for t in ULB_TYPES.values()}
    for row in read_csv(lgd["urban_local_bodies"]):
        kind = ULB_TYPES.get(row["Localbody Type Code"])
        if not kind:
            continue
        code = row["Local Body Code"]
        census = row["Census 2011 Code"]
        district = coverage[code]["district"]
        if district not in districts:
            stats[kind]["no_district"] += 1
            continue

        source = None
        if sbm_geoms.get(census):
            geom, source = dissolve(sbm_geoms[census]), "sbm"
        elif town_geoms.get(census):
            geom, source = dissolve(town_geoms[census]), "census_town"
        else:
            geom = dissolve([g for v in coverage[code]["villages"] for g in village_geoms.get(v, [])])
            source = "covered_villages" if geom else None
        point = None
        if geom is None:
            point = point_by_village.get(census) or village_point(coverage[code]["villages"])
            source = "village_point" if point else None
        if geom is None and point is None:
            geom, source = same_named_village(district, row["Local Body Name (In English)"])
        stats[kind][source or "none"] += 1

        ulbs[kind].append({
            "lgd": int(code),
            "district": int(district),
            "name": clean(row["Local Body Name (In English)"]),
            "name_local": row["Local Body Name (In Local)"].strip(),
            "coordinates": to_points(geom, MAX_POINTS[kind]) if geom else ([point] if point else []),
            "boundary_source": source,
        })

    # -- PRIs: District Panchayat -> Block Panchayat (union) -> Gram Panchayat
    pri = list(read_csv(lgd["pri_local_bodies"]))
    district_panchayat_to_district = {}
    for row in pri:
        if row["Localbody Type Code"] == "1":
            dist = district_by_key.get(key(row["Localbody Name (In English)"]))
            if dist:
                district_panchayat_to_district[row["Localbody Code"]] = dist
            else:
                print("unmatched district panchayat:", row["Localbody Name (In English)"])

    unions = {}
    for row in pri:
        if row["Localbody Type Code"] != "2":
            continue
        dist = district_panchayat_to_district.get(row["Parent Localbody Code"])
        if not dist:
            stats["panchayat_union"]["no_district"] += 1
            continue
        unions[row["Localbody Code"]] = {
            "lgd": int(row["Localbody Code"]),
            "district": int(dist),
            "name": clean(row["Localbody Name (In English)"]),
            "name_local": row["Localbody Name (In Local)"].strip(),
            "_geom": dissolve(block_geoms.get(row["Localbody Code"], [])),
        }

    panchayats = []
    vp_geoms_by_union = defaultdict(list)
    for row in pri:
        if row["Localbody Type Code"] != "3":
            continue
        union = unions.get(row["Parent Localbody Code"])
        if not union:
            stats["panchayat"]["no_union"] += 1
            continue
        code = row["Localbody Code"]
        if gp_geoms.get(code):
            geom, source = dissolve(gp_geoms[code]), "gp"
        else:
            geom = dissolve([g for v in gp_villages.get(code, ()) for g in village_geoms.get(v, [])])
            source = "mapped_villages" if geom else None
        point = None
        if geom is None:
            point = point_by_gp.get(code) or village_point(gp_villages.get(code, ()))
            source = "village_point" if point else None
        if geom is None and point is None:
            geom, source = same_named_village(union["district"], row["Localbody Name (In English)"])
        stats["panchayat"][source or "none"] += 1
        if geom is not None:
            vp_geoms_by_union[row["Parent Localbody Code"]].append(geom)
        panchayats.append({
            "lgd": int(code),
            "district": union["district"],
            "union": union["lgd"],
            "name": clean(row["Localbody Name (In English)"]),
            "name_local": row["Localbody Name (In Local)"].strip(),
            "coordinates": to_points(geom, MAX_POINTS["panchayat"]) if geom else ([point] if point else []),
            "boundary_source": source,
        })

    union_list = []
    for code, union in unions.items():
        geom, source = union.pop("_geom"), "block"
        if geom is None:
            geom = dissolve(vp_geoms_by_union.get(code, []))
            source = "member_panchayats" if geom else None
        if geom is None:
            geom, source = same_named_village(union["district"], union["name"])
        stats["panchayat_union"][source or "none"] += 1
        union["coordinates"] = to_points(geom, MAX_POINTS["panchayat_union"])
        union["boundary_source"] = source
        union_list.append(union)

    sort = lambda items: sorted(items, key=lambda x: (x["district"], x["name"], x["lgd"]))
    payload = {
        "meta": {
            "state": "Tamil Nadu",
            "generated": datetime.date.today().isoformat(),
            "lgd_snapshots": lgd_dates,
            "coordinates": "[[latitude, longitude], ...] closed outer ring",
            "sources": [
                "Local Government Directory (lgdirectory.gov.in) via github.com/ramSeraph/opendata",
                "LGD/SBM boundaries via github.com/ramSeraph/indian_admin_boundaries",
            ],
            "stats": {k: dict(v) for k, v in stats.items()},
        },
        "districts": sorted(districts.values(), key=lambda d: d["name"]),
        "corporations": sort(ulbs["corporation"]),
        "municipalities": sort(ulbs["municipality"]),
        "town_panchayats": sort(ulbs["town_panchayat"]),
        "panchayat_unions": sort(union_list),
        "panchayats": sort(panchayats),
    }
    with gzip.open(out_path, "wt", encoding="utf-8", compresslevel=9) as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    for kind, counts in payload["meta"]["stats"].items():
        print(f"{kind:16} {dict(counts)}")
    print(f"wrote {out_path} ({os.path.getsize(out_path) / 1e6:.1f} MB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", required=True, help="directory for downloaded source files")
    parser.add_argument(
        "--out",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "tn_local_bodies.json.gz"),
    )
    args = parser.parse_args()
    build(args.cache, args.out)

from django.conf import settings
import requests


class OpenRouteServiceError(Exception):
    pass


def route_stops(stops, vehicle_start=None):
    api_key = settings.ORS_API_KEY
    if not api_key or not stops:
        return {
            "distance": 0,
            "duration": 0,
            "geometry": None,
            "vehicle_start": vehicle_start,
        }
    start = vehicle_start or stops[0]["location"]
    coordinates = [start, *[stop["location"] for stop in stops]]
    geometry = _directions_geometry(coordinates, _headers(api_key))
    return {
        "distance": _summary_value(geometry, "distance"),
        "duration": _summary_value(geometry, "duration"),
        "geometry": geometry,
        "vehicle_start": start,
    }


def optimize_stops(stops, vehicle_start=None):
    api_key = settings.ORS_API_KEY
    if not api_key:
        raise OpenRouteServiceError("ORS_API_KEY is not configured.")
    if not stops:
        return {
            "ordered_ids": [],
            "distance": 0,
            "duration": 0,
            "geometry": None,
            "route_legs": [],
            "vehicle_start": vehicle_start,
        }

    start = vehicle_start or stops[0]["location"]
    if len(stops) == 1:
        coordinates = [start, stops[0]["location"]] if start != stops[0]["location"] else []
        geometry = _directions_geometry(coordinates, _headers(api_key)) if coordinates else None
        return {
            "ordered_ids": [stops[0]["id"]],
            "distance": _summary_value(geometry, "distance"),
            "duration": _summary_value(geometry, "duration"),
            "geometry": geometry,
            "route_legs": _route_legs(geometry, [stops[0]["id"]]),
            "vehicle_start": start,
        }

    jobs = [
        {"id": index + 1, "location": stop["location"]}
        for index, stop in enumerate(stops)
    ]
    payload = {
        "jobs": jobs,
        "vehicles": [{"id": 1, "profile": "driving-car", "start": start}],
    }
    headers = _headers(api_key)

    try:
        response = requests.post(
            settings.ORS_OPTIMIZATION_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        route = response.json()["routes"][0]
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        raise OpenRouteServiceError(f"OpenRouteService optimization failed: {exc}") from exc

    ordered_indexes = [
        step["job"] - 1
        for step in route.get("steps", [])
        if step.get("type") == "job" and step.get("job")
    ]
    ordered_indexes.extend(
        index for index in range(len(stops)) if index not in ordered_indexes
    )
    ordered_stops = [stops[index] for index in ordered_indexes]
    route_coordinates = [start, *[stop["location"] for stop in ordered_stops]]
    geometry = _directions_geometry(route_coordinates, headers)

    return {
        "ordered_ids": [stop["id"] for stop in ordered_stops],
        "distance": route.get("distance", 0),
        "duration": route.get("duration", 0),
        "geometry": geometry,
        "route_legs": _route_legs(
            geometry,
            [stop["id"] for stop in ordered_stops],
        ),
        "vehicle_start": start,
    }


def _headers(api_key):
    return {"Authorization": api_key, "Content-Type": "application/json"}


def _summary_value(geometry, key):
    try:
        return geometry["features"][0]["properties"]["summary"][key]
    except (KeyError, IndexError, TypeError):
        return 0


def _route_legs(geometry, ordered_ids):
    try:
        feature = geometry["features"][0]
        coordinates = feature["geometry"]["coordinates"]
        segments = feature["properties"]["segments"]
    except (KeyError, IndexError, TypeError):
        return []

    legs = []
    for index, segment in enumerate(segments):
        if index >= len(ordered_ids):
            break
        steps = segment.get("steps") or []
        if not steps:
            continue
        start_index = steps[0].get("way_points", [0, 0])[0]
        end_index = steps[-1].get("way_points", [0, 0])[-1]
        leg_coordinates = coordinates[start_index:end_index + 1]
        if len(leg_coordinates) < 2:
            continue
        legs.append({
            "destination_id": ordered_ids[index],
            "distance": segment.get("distance", 0),
            "duration": segment.get("duration", 0),
            "geometry": {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "LineString",
                    "coordinates": leg_coordinates,
                },
            },
        })
    return legs


def _directions_geometry(coordinates, headers):
    if len(coordinates) < 2:
        return None
    try:
        response = requests.post(
            settings.ORS_DIRECTIONS_URL,
            json={"coordinates": coordinates},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, TypeError, ValueError):
        return None

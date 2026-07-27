import math


def coordinates(*points):
    return [
        {"latitude": float(latitude), "longitude": float(longitude)}
        for latitude, longitude in points
    ]


def spread_points(center_lat, center_lon, count, radius_km=1.0):
    """`count` deterministic points spread around (center_lat, center_lon)
    within `radius_km`, derived purely from each point's index (no
    randomness), so re-running a seeder that consumes this produces the
    exact same coordinates every time. Returns [(lat, lon), ...], index
    0..count-1, as plain floats rounded to 6 decimal places."""
    points = []
    for i in range(count):
        angle = (2 * math.pi / count) * i
        radius = radius_km * (0.3 + 0.7 * (i % 4) / 3.0)
        d_lat = (radius / 111.0) * math.cos(angle)
        d_lon = (radius / (111.0 * math.cos(math.radians(center_lat)))) * math.sin(angle)
        points.append((round(center_lat + d_lat, 6), round(center_lon + d_lon, 6)))
    return points

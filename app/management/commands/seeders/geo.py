import math
import hashlib


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


def _deterministic_offset(seed_str, index, max_offset=0.002):
    """Generate a deterministic pseudo-random offset using hash."""
    hash_input = f"{seed_str}:{index}".encode()
    hash_val = int(hashlib.md5(hash_input).hexdigest(), 16)
    # Normalize to [-1, 1] then scale
    normalized = (hash_val % 20000) / 10000.0 - 1.0
    return normalized * max_offset


def generate_ward_geofence(center_lat, center_lon, ward_name, parent_name, num_points=8, base_radius_km=0.6):
    """
    Generate a realistic-looking polygon geofence for a ward.
    
    Creates an organic polygon by:
    - Using deterministic pseudo-random offsets based on ward+parent name
    - Varying radius per point for organic shape
    - Ensuring polygon is closed (first point = last point)
    
    Args:
        center_lat, center_lon: Ward centroid coordinates
        ward_name: Ward name for deterministic seed
        parent_name: Parent local body name for deterministic seed
        num_points: Number of vertices (default 8 for organic shape)
        base_radius_km: Base radius in km (default 0.6km ~ ward size)
    
    Returns:
        List of [lat, lon] dicts forming a closed polygon
    """
    seed = f"{parent_name}:{ward_name}"
    points = []
    
    for i in range(num_points):
        angle = (2 * math.pi / num_points) * i
        
        # Vary radius per point for organic shape (deterministic)
        radius_variation = 0.7 + 0.3 * ((i * 3) % 7) / 7.0  # 0.7 to 1.0
        radius = base_radius_km * radius_variation
        
        # Add small deterministic jitter
        jitter_lat = _deterministic_offset(seed, i * 2, max_offset=0.001)
        jitter_lon = _deterministic_offset(seed, i * 2 + 1, max_offset=0.001)
        
        d_lat = (radius / 111.0) * math.cos(angle) + jitter_lat
        d_lon = (radius / (111.0 * math.cos(math.radians(center_lat)))) * math.sin(angle) + jitter_lon
        
        lat = round(center_lat + d_lat, 6)
        lon = round(center_lon + d_lon, 6)
        points.append((lat, lon))
    
    # Close the polygon
    points.append(points[0])
    
    return coordinates(*points)

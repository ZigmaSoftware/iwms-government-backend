def coordinates(*points):
    return [
        {"latitude": float(latitude), "longitude": float(longitude)}
        for latitude, longitude in points
    ]

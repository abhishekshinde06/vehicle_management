from math import radians, sin, cos, sqrt, atan2
from app.core.config import settings

def calculate_distance_m(lat1, lon1, lat2, lon2):
    """Calculate distance between two GPS points in meters."""

    earth_radius = 6371000

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius * c

def verify_geofence(
    operator_lat: float,
    operator_lon: float,
    pump_lat: float,
    pump_lon: float,
    gps_accuracy: float,
    radius: float | None = None,
) -> bool:
    """
    Verify that operator GPS is accurate and inside pump radius.
    """

    # Validate GPS coordinates
    if not (-90 <= operator_lat <= 90 and -180 <= operator_lon <= 180):
        return False

    if not (-90 <= pump_lat <= 90 and -180 <= pump_lon <= 180):
        return False

    # Reject inaccurate GPS readings
    if not (0 <= gps_accuracy <= settings.MAX_ALLOWED_GPS_ACCURACY_METERS):
        return False

    # Use configured radius if pump-specific radius isn't provided
    allowed_radius = (
        radius
        if radius is not None
        else settings.DEFAULT_GEOFENCE_RADIUS_METERS
    )

    if not (0 < allowed_radius < float("inf")):
        return False

    # Calculate actual distance
    distance = calculate_distance_m(
        operator_lat,
        operator_lon,
        pump_lat,
        pump_lon,
    )

    return distance + gps_accuracy <= allowed_radius
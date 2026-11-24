from app.core.geofence import verify_geofence


def test_operator_inside_pump():
    """Operator at pump with accurate GPS should pass."""
    assert verify_geofence(
        23.2599, 77.4126,
        23.2599, 77.4126,
        gps_accuracy=10
    ) is True


def test_operator_outside_pump():
    """Operator far from pump should be rejected."""
    assert verify_geofence(
        23.2599, 77.4126,
        23.2700, 77.4200,
        gps_accuracy=10
    ) is False


def test_inaccurate_gps():
    """GPS accuracy above configured limit should fail."""
    assert verify_geofence(
        23.2599, 77.4126,
        23.2599, 77.4126,
        gps_accuracy=80
    ) is False


def test_invalid_coordinates():
    """Latitude outside -90 to 90 should fail."""
    assert verify_geofence(
        100, 77.4126,
        23.2599, 77.4126,
        gps_accuracy=10
    ) is False


def test_boundary_accuracy():
    """Location uncertainty must fit inside allowed radius."""
    assert verify_geofence(
        23.2599, 77.4126,
        23.2599, 77.4126,
        gps_accuracy=10,
        radius=5
    ) is False
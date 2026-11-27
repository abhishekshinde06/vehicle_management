import pytest
from pydantic import ValidationError

from app.schemas.fuel_entry import FuelEntryCreate


def make_payload(photos):
    return {
        "vehicle_id": "vehicle-1",
        "petrol_pump_id": "pump-1",
        "gps_verification_token": "test-gps-token",
        "current_odometer": 1100,
        "fuel_litres": 20,
        "latitude": 23.2599,
        "longitude": 77.4126,
        "accuracy_m": 10,
        "photos": photos,
    }


def test_valid_photo_types():
    photos = [
        {"photo_type": "PLATE", "photo_url": "plate.jpg"},
        {"photo_type": "ODOMETER", "photo_url": "odometer.jpg"},
        {"photo_type": "RECEIPT", "photo_url": "receipt.jpg"},
    ]

    entry = FuelEntryCreate(**make_payload(photos))
    assert len(entry.photos) == 3


def test_duplicate_photo_types():
    photos = [
        {"photo_type": "PLATE", "photo_url": "plate1.jpg"},
        {"photo_type": "PLATE", "photo_url": "plate2.jpg"},
        {"photo_type": "RECEIPT", "photo_url": "receipt.jpg"},
    ]

    with pytest.raises(ValidationError):
        FuelEntryCreate(**make_payload(photos))


def test_missing_photos():
    with pytest.raises(ValidationError):
        FuelEntryCreate(**make_payload([]))


def test_empty_photo_url():
    photos = [
        {"photo_type": "PLATE", "photo_url": ""},
        {"photo_type": "ODOMETER", "photo_url": "odometer.jpg"},
        {"photo_type": "RECEIPT", "photo_url": "receipt.jpg"},
    ]

    with pytest.raises(ValidationError):
        FuelEntryCreate(**make_payload(photos))


def test_duplicate_photo_urls():
    """Duplicate photo URLs must be rejected."""
    photos = [
        {"photo_type": "PLATE", "photo_url": "same_image.jpg"},
        {"photo_type": "ODOMETER", "photo_url": "same_image.jpg"},
        {"photo_type": "RECEIPT", "photo_url": "receipt.jpg"},
    ]

    with pytest.raises(ValidationError) as exc_info:
        FuelEntryCreate(**make_payload(photos))

    assert "Duplicate photo URLs are not allowed" in str(
        exc_info.value
    )


def test_whitespace_photo_url():
    """Blank or whitespace-only photo URLs must be rejected."""
    photos = [
        {"photo_type": "PLATE", "photo_url": "   "},
        {"photo_type": "ODOMETER", "photo_url": "odometer.jpg"},
        {"photo_type": "RECEIPT", "photo_url": "receipt.jpg"},
    ]

    with pytest.raises(ValidationError):
        FuelEntryCreate(**make_payload(photos))


def test_unexpected_request_fields():
    """Unexpected request fields must be rejected."""
    photos = [
        {"photo_type": "PLATE", "photo_url": "plate.jpg"},
        {"photo_type": "ODOMETER", "photo_url": "odometer.jpg"},
        {"photo_type": "RECEIPT", "photo_url": "receipt.jpg"},
    ]

    payload = make_payload(photos)
    payload["unexpected_field"] = "malicious_data"

    with pytest.raises(ValidationError) as exc_info:
        FuelEntryCreate(**payload)

    assert "Extra inputs are not permitted" in str(
        exc_info.value
    )


def test_legacy_direct_fields_rejected():
    """Legacy direct photo URL fields must be rejected."""
    photos = [
        {"photo_type": "PLATE", "photo_url": "plate.jpg"},
        {"photo_type": "ODOMETER", "photo_url": "odometer.jpg"},
        {"photo_type": "RECEIPT", "photo_url": "receipt.jpg"},
    ]

    payload = make_payload(photos)
    payload["photo_plate_url"] = "legacy_plate.jpg"

    with pytest.raises(ValidationError) as exc_info:
        FuelEntryCreate(**payload)

    assert "Extra inputs are not permitted" in str(
        exc_info.value
    )


@pytest.mark.parametrize(
    "field_name",
    [
        "current_odometer",
        "fuel_litres",
        "accuracy_m",
        "latitude",
        "longitude",
    ],
)
def test_nan_numeric_values_rejected(field_name):
    """NaN numeric values must be rejected."""
    photos = [
        {"photo_type": "PLATE", "photo_url": "plate.jpg"},
        {"photo_type": "ODOMETER", "photo_url": "odometer.jpg"},
        {"photo_type": "RECEIPT", "photo_url": "receipt.jpg"},
    ]

    payload = make_payload(photos)
    payload[field_name] = float("nan")

    with pytest.raises(ValidationError):
        FuelEntryCreate(**payload)


@pytest.mark.parametrize(
    "field_name",
    [
        "current_odometer",
        "fuel_litres",
        "accuracy_m",
        "latitude",
        "longitude",
    ],
)
def test_infinite_numeric_values_rejected(field_name):
    """Infinite numeric values must be rejected."""
    photos = [
        {"photo_type": "PLATE", "photo_url": "plate.jpg"},
        {"photo_type": "ODOMETER", "photo_url": "odometer.jpg"},
        {"photo_type": "RECEIPT", "photo_url": "receipt.jpg"},
    ]

    payload = make_payload(photos)
    payload[field_name] = float("inf")

    with pytest.raises(ValidationError):
        FuelEntryCreate(**payload)


@pytest.mark.parametrize("token", [None, ""])
def test_invalid_gps_token_field(token):
    """Missing or empty GPS tokens must be rejected."""
    photos = [
        {"photo_type": "PLATE", "photo_url": "plate.jpg"},
        {"photo_type": "ODOMETER", "photo_url": "odometer.jpg"},
        {"photo_type": "RECEIPT", "photo_url": "receipt.jpg"},
    ]

    payload = make_payload(photos)

    if token is None:
        payload.pop("gps_verification_token")
    else:
        payload["gps_verification_token"] = token

    with pytest.raises(ValidationError) as exc_info:
        FuelEntryCreate(**payload)

    assert any(
        error["loc"] == ("gps_verification_token",)
        for error in exc_info.value.errors()
    )
import pytest
from pydantic import ValidationError

from app.schemas.fuel_entry import FuelEntryCreate


def make_payload(photos):
    return {
        "vehicle_id": "vehicle-1",
        "petrol_pump_id": "pump-1",
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
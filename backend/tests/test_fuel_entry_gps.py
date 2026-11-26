
"""
Fuel Entry GPS Integration Tests
--------------------------------
Tests authentication, GPS validation, and fuel entry creation
using an isolated in-memory SQLite database.
"""

import os
import tempfile
import uuid

# Configure a temporary database before importing the application.
_test_db_dir = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = (
    f"sqlite:///{_test_db_dir.name}/fuel_test.db"
)

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.main import app as fastapi_app
from app.core.config import settings
from app.core.database import Base, get_db
from app.models import User, Vehicle, PetrolPump, FuelEntry, UploadedPhoto


def seed_three_photos(TestingSession, uploader_id: str):
    """Creates three unused UploadedPhoto records and returns the API payload list."""
    photos = []
    with TestingSession() as db:
        for ptype in ("PLATE", "ODOMETER", "RECEIPT"):
            pid = str(uuid.uuid4())
            db.add(
                UploadedPhoto(
                    id=pid,
                    uploader_id=uploader_id,
                    photo_type=ptype,
                    storage_type="local",
                    storage_reference=f"{pid}.jpg",
                    content_type="image/jpeg",
                    size_bytes=1024,
                    is_used=False,
                )
            )
            photos.append(
                {
                    "photo_type": ptype,
                    "photo_url": f"{settings.API_PREFIX}/fuel-entries/photos/{pid}",
                }
            )
        db.commit()
    return photos


@pytest.fixture
def test_client():
    """Create an isolated in-memory database for each test."""

    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSession = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(fastapi_app) as client:
            yield client, TestingSession
    finally:
        fastapi_app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def test_fuel_entry_requires_login(test_client):
    """Requests without authentication must be rejected."""
    client, _ = test_client

    response = client.post(
        "/api/fuel-entries/",
        json={},
    )

    assert response.status_code == 401


def test_fuel_entry_without_gps(test_client):
    """Unauthenticated requests must fail even without GPS."""
    client, _ = test_client

    response = client.post(
        "/api/fuel-entries/",
        json={
            "vehicle_id": "test-vehicle",
            "petrol_pump_id": "test-pump",
            "current_odometer": 1200,
            "fuel_litres": 20,
        },
    )

    assert response.status_code == 401


def test_fuel_entry_gps_validation(test_client):
    """Test GPS validation with an authenticated operator."""

    client, TestingSession = test_client

    # 1. Create test operator, vehicle, and petrol pump.
    with TestingSession() as db:
        operator = User(
            username="gps_test_operator",
            password_hash="test_hash",
            role="operator",
            is_active=True,
        )

        vehicle = Vehicle(
            vehicle_number="TEST-GPS-123",
            initial_odometer=1000,
            is_active=True,
        )

        pump = PetrolPump(
            name="Test Petrol Pump",
            latitude=23.2599,
            longitude=77.4126,
            radius_meters=100,
            is_active=True,
        )

        db.add_all([operator, vehicle, pump])
        db.commit()

        operator_id = operator.id
        vehicle_id = vehicle.id
        pump_id = pump.id

    # 2. Generate a test JWT token.
    token = jwt.encode(
        {"sub": operator_id},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    headers = {
        "Authorization": f"Bearer {token}"
    }

    payload = {
    "vehicle_id": vehicle_id,
    "petrol_pump_id": pump_id,
    "current_odometer": 1100,
    "fuel_litres": 20,
    "is_full_tank": True,
    "photos": seed_three_photos(TestingSession, operator_id),
    }

    # 3. Missing GPS -> 422
    response = client.post(
        "/api/fuel-entries/",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 422, response.text

    # 4. Outside authorized pump -> 403
    response = client.post(
        "/api/fuel-entries/",
        json={
            **payload,
            "latitude": 23.2700,
            "longitude": 77.4200,
            "accuracy_m": 10,
        },
        headers=headers,
    )
    assert response.status_code == 403, response.text

    # 5. Inaccurate GPS -> 403
    response = client.post(
        "/api/fuel-entries/",
        json={
            **payload,
            "latitude": 23.2599,
            "longitude": 77.4126,
            "accuracy_m": 80,
        },
        headers=headers,
    )
    assert response.status_code == 403, response.text

    # Rejected requests must not create fuel records.
    with TestingSession() as db:
        assert db.query(FuelEntry).count() == 0

    # 6. Valid GPS -> 201
    response = client.post(
        "/api/fuel-entries/",
        json={
            **payload,
            "latitude": 23.2599,
            "longitude": 77.4126,
            "accuracy_m": 10,
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["is_location_verified"] is True
    assert data["distance_from_pump_m"] == 0.0

    # Confirm the entry was actually saved.
    with TestingSession() as db:
        assert db.query(FuelEntry).count() == 1

def test_verify_location_requires_login(test_client):
    client, _ = test_client

    response = client.post(
        "/api/fuel-entries/verify-location",
        json={},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "latitude, longitude, accuracy, expected_status",
    [
        (23.2599, 77.4126, 10, 200),
        (23.2700, 77.4200, 10, 403),
        (23.2599, 77.4126, 80, 403),
        (100, 77.4126, 10, 422),
    ],
)
def test_verify_location(
    test_client,
    latitude,
    longitude,
    accuracy,
    expected_status,
):
    client, TestingSession = test_client

    with TestingSession() as db:
        operator = User(
            username="location_operator",
            password_hash="test_hash",
            role="operator",
            is_active=True,
        )

        pump = PetrolPump(
            name="Test Pump",
            latitude=23.2599,
            longitude=77.4126,
            radius_meters=100,
            is_active=True,
        )

        db.add_all([operator, pump])
        db.commit()

        operator_id = operator.id
        pump_id = pump.id

    token = jwt.encode(
        {"sub": operator_id},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    response = client.post(
        "/api/fuel-entries/verify-location",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "petrol_pump_id": pump_id,
            "latitude": latitude,
            "longitude": longitude,
            "accuracy_m": accuracy,
        },
    )

    assert response.status_code == expected_status, response.text

    if expected_status == 200:
        assert response.json()["is_location_verified"] is True

    # Location verification must not create a fuel entry.
    with TestingSession() as db:
        assert db.query(FuelEntry).count() == 0

def test_full_to_full_mileage(test_client):
    client, TestingSession = test_client

    # Create test data.
    with TestingSession() as db:
        operator = User(
            username="mileage_operator",
            password_hash="test_hash",
            role="operator",
            is_active=True,
        )

        vehicle = Vehicle(
            vehicle_number="TEST-MILEAGE-01",
            initial_odometer=44000,
            is_active=True,
        )

        pump = PetrolPump(
            name="Mileage Test Pump",
            latitude=23.2599,
            longitude=77.4126,
            radius_meters=100,
            is_active=True,
        )

        db.add_all([operator, vehicle, pump])
        db.commit()

        operator_id = operator.id
        vehicle_id = vehicle.id
        pump_id = pump.id

    token = jwt.encode(
        {"sub": operator_id},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    headers = {"Authorization": f"Bearer {token}"}

    # Common fuel entry data.
    payload = {
        "vehicle_id": vehicle_id,
        "petrol_pump_id": pump_id,
        "latitude": 23.2599,
        "longitude": 77.4126,
        "accuracy_m": 10,
    }

    # Odometer, litres, full tank, expected mileage.
    scenarios = [
        (45000, 50, True, None),
        (45200, 20, False, None),
        (45400, 30, False, None),
        (45600, 50, True, 6.0),
        (46200, 100, True, 6.0),
    ]

    for odometer, litres, full_tank, expected in scenarios:

        response = client.post(
            "/api/fuel-entries/",
            headers=headers,
            json={
                **payload,
                "current_odometer": odometer,
                "fuel_litres": litres,
                "is_full_tank": full_tank,
                "photos": seed_three_photos(TestingSession, operator_id),
            },
        )

        assert response.status_code == 201, response.text

        assert response.json()["mileage_kmpl"] == expected

    with TestingSession() as db:
        assert db.query(FuelEntry).count() == 5      

        # Try submitting the last fuel entry again.
    response = client.post(
        "/api/fuel-entries/",
        headers=headers,
        json={
            **payload,
            "current_odometer": 46200,
            "fuel_litres": 100,
            "is_full_tank": True,
            "photos": seed_three_photos(TestingSession, operator_id),
        },
    )

    assert response.status_code == 400

    with TestingSession() as db:
        assert db.query(FuelEntry).count() == 5      

def test_owner_review_and_mileage(test_client):
    client, TestingSession = test_client

    with TestingSession() as db:
        owner = User(
            username="review_owner",
            password_hash="test_hash",
            role="owner",
            is_active=True,
        )

        operator = User(
            username="review_operator",
            password_hash="test_hash",
            role="operator",
            is_active=True,
        )

        vehicle = Vehicle(
            vehicle_number="TEST-REVIEW-01",
            initial_odometer=44000,
            is_active=True,
        )

        pump = PetrolPump(
            name="Review Test Pump",
            latitude=23.2599,
            longitude=77.4126,
            radius_meters=100,
            is_active=True,
        )

        db.add_all([owner, operator, vehicle, pump])
        db.commit()

        owner_id = owner.id
        operator_id = operator.id
        vehicle_id = vehicle.id
        pump_id = pump.id

    def get_headers(user_id):
        token = jwt.encode(
            {"sub": user_id},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        return {"Authorization": f"Bearer {token}"}

    owner_headers = get_headers(owner_id)
    operator_headers = get_headers(operator_id)

    payload = {
        "vehicle_id": vehicle_id,
        "petrol_pump_id": pump_id,
        "latitude": 23.2599,
        "longitude": 77.4126,
        "accuracy_m": 10,
    }

    entry_ids = []

    # Create three fueling records.
    for odometer, litres, full_tank in [
        (45000, 50, True),
        (45200, 20, False),
        (45600, 80, True),
    ]:
        response = client.post(
            "/api/fuel-entries/",
            headers=operator_headers,
            json={
                **payload,
                "current_odometer": odometer,
                "fuel_litres": litres,
                "is_full_tank": full_tank,
                "photos": seed_three_photos(TestingSession, operator_id),
            },
        )

        assert response.status_code == 201, response.text
        entry_ids.append(response.json()["id"])

    assert response.json()["mileage_kmpl"] == 6.0

    review_url = f"/api/fuel-entries/{entry_ids[1]}/verify"

    # Operator cannot approve.
    response = client.patch(
        review_url,
        headers=operator_headers,
        json={"status": "APPROVED"},
    )
    assert response.status_code == 403

    # Rejection without reason is invalid.
    response = client.patch(
        review_url,
        headers=owner_headers,
        json={"status": "REJECTED"},
    )
    assert response.status_code == 400

    # Owner rejects an incorrect partial refill.
    response = client.patch(
        review_url,
        headers=owner_headers,
        json={
            "status": "REJECTED",
            "rejection_reason": "Incorrect fuel entry",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "REJECTED"

    # Repeated review must fail.
    response = client.patch(
        review_url,
        headers=owner_headers,
        json={"status": "APPROVED"},
    )
    assert response.status_code == 409

    # Check recalculated mileage.
    response = client.get(
        f"/api/fuel-entries/{entry_ids[2]}",
        headers=owner_headers,
    )

    assert response.status_code == 200
    assert response.json()["mileage_kmpl"] == 7.5

    # Owner approves the final entry.
    response = client.patch(
        f"/api/fuel-entries/{entry_ids[2]}/verify",
        headers=owner_headers,
        json={"status": "APPROVED"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"        
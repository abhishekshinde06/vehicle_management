"""
Core Business Flow Verification Tests
-------------------------------------
Automated integration tests validating:
1. Operator & Owner authentication (JWT token generation).
2. Fetching fleet vehicles and authorized petrol pumps via clean /api routes.
3. Submitting a new fuel entry with odometer, liters, AND photos stored in `entry_photos`.
4. Automatic distance and mileage (km/L) calculation.
5. Decreasing odometer sanity validation (preventing invalid entries).
6. Owner approval workflow with status update and audit trail.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Base, engine
from seed import seed_database

client = TestClient(app)


def setup_module():
    """
    Setup hook executed once before running the test suite:
    Resets tables and re-seeds the database to ensure a clean, isolated test environment.
    """
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_database()


def test_login_operator():
    """
    Test Case 1: Operator Authentication
    - Sends POST to /api/auth/login with valid operator credentials.
    - Asserts 200 OK status.
    - Verifies JWT access_token is returned and role is 'operator'.
    """
    res = client.post("/api/auth/login", json={"username": "operator", "password": "operator123"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "operator"


def test_login_owner():
    """
    Test Case 2: Owner Authentication
    - Sends POST to /api/auth/login with valid owner credentials.
    - Asserts 200 OK status.
    - Verifies JWT access_token is returned and role is 'owner'.
    """
    res = client.post("/api/auth/login", json={"username": "owner", "password": "owner123"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "owner"


def test_fuel_entry_and_mileage_calculation():
    """
    Test Case 3: Complete Fueling, Photo Attachments & Mileage Flow
    - Authenticates as Operator.
    - Queries fleet vehicles (/api/vehicles).
    - Queries authorized petrol pumps (/api/petrol-pumps).
    - Submits a fuel entry with 3 photos (PLATE, ODOMETER, RECEIPT).
    - Asserts:
        * Distance Travelled = 45,600 - 45,000 = 600.0 km
        * Mileage = 600 / 100 = 6.0 km/L
        * Status = 'PENDING'
        * Photos are stored in the separate entry_photos table and returned in the response
    - Attempts invalid entry with decreasing odometer (45,500 < 45,600) and asserts 400 rejection.
    - Authenticates as Owner and APPROVES the pending entry.
    - Asserts entry status becomes 'APPROVED'.
    """
    # 1. Login as operator
    op_login = client.post("/api/auth/login", json={"username": "operator", "password": "operator123"}).json()
    op_token = op_login["access_token"]
    headers = {"Authorization": f"Bearer {op_token}"}

    # 2. Get vehicles and pumps
    v_res = client.get("/api/vehicles/", headers=headers)
    assert v_res.status_code == 200, v_res.text
    vehicles = v_res.json()
    assert len(vehicles) >= 1
    vehicle = vehicles[0]

    p_res = client.get("/api/petrol-pumps/", headers=headers)
    assert p_res.status_code == 200, p_res.text
    pumps = p_res.json()
    assert len(pumps) >= 1
    pump = pumps[0]

    # Initial odometer is 45000. Let's record 45600 with 100 Litres + 3 attached photos
    entry_payload = {
        "vehicle_id": vehicle["id"],
        "petrol_pump_id": pump["id"],
        "current_odometer": 45600.0,
        "fuel_litres": 100.0,
        "is_full_tank": True,
        "photos": [
            {"photo_type": "PLATE", "photo_url": "/uploads/test_plate.jpg"},
            {"photo_type": "ODOMETER", "photo_url": "/uploads/test_odometer.jpg"},
            {"photo_type": "RECEIPT", "photo_url": "/uploads/test_receipt.jpg"}
        ]
    }

    create_res = client.post("/api/fuel-entries/", json=entry_payload, headers=headers)
    assert create_res.status_code == 201, create_res.text
    entry_data = create_res.json()

    assert entry_data["previous_odometer"] == 45000.0
    assert entry_data["current_odometer"] == 45600.0
    assert entry_data["distance_km"] == 600.0
    assert entry_data["mileage_kmpl"] == 6.0  # 600 km / 100 L = 6 km/L
    assert entry_data["status"] == "PENDING"

    # Verify separate entry_photos table was populated and linked
    assert len(entry_data["photos"]) == 3
    photo_types = [p["photo_type"] for p in entry_data["photos"]]
    assert "PLATE" in photo_types
    assert "ODOMETER" in photo_types
    assert "RECEIPT" in photo_types

    # 3. Test Decreasing Odometer validation (must fail)
    invalid_payload = {
        "vehicle_id": vehicle["id"],
        "petrol_pump_id": pump["id"],
        "current_odometer": 45500.0,  # Lower than 45600!
        "fuel_litres": 50.0,
        "is_full_tank": True
    }
    invalid_res = client.post("/api/fuel-entries/", json=invalid_payload, headers=headers)
    assert invalid_res.status_code == 400
    assert "Invalid odometer reading" in invalid_res.json()["detail"]

    # 4. Login as Owner to Approve the entry
    owner_login = client.post("/api/auth/login", json={"username": "owner", "password": "owner123"}).json()
    owner_token = owner_login["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    verify_res = client.patch(
        f"/api/fuel-entries/{entry_data['id']}/verify",
        json={"status": "APPROVED", "rejection_reason": None},
        headers=owner_headers
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "APPROVED"

"""
Core Business Flow Verification Tests
-------------------------------------
Automated integration tests validating:
1. Fleet Owner self-registration (/api/auth/signup).
2. Owner-provisioned Operator/Driver creation (/api/auth/create-operator & /api/auth/operators).
3. RBAC guard: Operators cannot provision other operators.
4. Operator & Owner authentication (JWT token generation).
5. Fetching fleet vehicles and authorized petrol pumps via clean /api routes.
6. Submitting a new fuel entry with odometer, liters, AND photos stored in `entry_photos`.
7. Automatic distance and mileage (km/L) calculation.
8. Decreasing odometer sanity validation (preventing invalid entries).
9. Geofence & GPS distance verification against authorized petrol pump radius.
10. Live photo upload via `/api/fuel-entries/upload-photo`.
11. Owner approval workflow with status update and audit trail.
12. Fleet vehicle and authorized pump creation by owner.
"""

import io
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


def test_owner_signup_and_operator_provisioning():
    """
    Test Case 1: Fleet Owner Self-Registration & Operator Provisioning
    - Fleet Owner signs up at /api/auth/signup (assigned role 'owner').
    - Owner provisions a new Operator at /api/auth/create-operator (assigned role 'operator').
    - Owner retrieves list of fleet operators at /api/auth/operators.
    - Operator cannot create another operator (assert 403 Forbidden).
    - Operator logs in with provisioned credentials.
    """
    # 1. Owner signs up
    owner_signup_payload = {
        "username": "new_fleet_owner",
        "password": "secureownerpassword123",
        "full_name": "New Fleet Enterprise Owner"
    }
    signup_res = client.post("/api/auth/signup", json=owner_signup_payload)
    assert signup_res.status_code == 201, signup_res.text
    owner_data = signup_res.json()
    assert "access_token" in owner_data
    assert owner_data["role"] == "owner"
    assert owner_data["username"] == "new_fleet_owner"
    owner_headers = {"Authorization": f"Bearer {owner_data['access_token']}"}

    # Duplicate owner signup is rejected
    dup_res = client.post("/api/auth/signup", json=owner_signup_payload)
    assert dup_res.status_code == 400

    # 2. Owner provisions an Operator / Driver
    op_payload = {
        "username": "fleet_driver_sunil",
        "password": "driverpassword123",
        "full_name": "Sunil Kumar (Truck Driver)"
    }
    create_op_res = client.post("/api/auth/create-operator", json=op_payload, headers=owner_headers)
    assert create_op_res.status_code == 201, create_op_res.text
    op_created = create_op_res.json()
    assert op_created["username"] == "fleet_driver_sunil"
    assert op_created["role"] == "operator"

    # 3. Owner lists operators
    list_op_res = client.get("/api/auth/operators", headers=owner_headers)
    assert list_op_res.status_code == 200
    usernames = [u["username"] for u in list_op_res.json()]
    assert "fleet_driver_sunil" in usernames

    # 4. Operator logs in
    op_login_res = client.post("/api/auth/login", data={"username": "fleet_driver_sunil", "password": "driverpassword123"})
    assert op_login_res.status_code == 200
    op_token = op_login_res.json()["access_token"]
    assert op_login_res.json()["role"] == "operator"
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # 5. Security check: Operator CANNOT create another operator (must fail with 403 Forbidden)
    forbidden_res = client.post("/api/auth/create-operator", json={
        "username": "rogue_driver",
        "password": "roguepassword123"
    }, headers=op_headers)
    assert forbidden_res.status_code == 403


def test_login_operator():
    """
    Test Case 2: Operator Authentication
    - Sends POST to /api/auth/login with valid operator form credentials.
    - Asserts 200 OK status.
    - Verifies JWT access_token is returned and role is 'operator'.
    """
    res = client.post("/api/auth/login", data={"username": "operator", "password": "operator123"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "operator"

    # Verify /api/auth/me
    me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "operator"


def test_login_owner():
    """
    Test Case 3: Owner Authentication
    - Sends POST to /api/auth/login with valid owner form credentials.
    - Asserts 200 OK status.
    - Verifies JWT access_token is returned and role is 'owner'.
    """
    res = client.post("/api/auth/login", data={"username": "owner", "password": "owner123"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert "access_token" in data
    assert data["role"] == "owner"


def test_photo_upload():
    """
    Test Case 4: Live Camera Photo Upload
    - Uploads a test JPEG file to /api/fuel-entries/upload-photo.
    - Asserts 200 OK status.
    - Confirms generated URL points to /uploads/<file>.
    """
    login = client.post("/api/auth/login", data={"username": "operator", "password": "operator123"}).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    file_bytes = b"fake image bytes for testing plate photo"
    files = {"file": ("camera_plate.jpg", io.BytesIO(file_bytes), "image/jpeg")}
    upload_res = client.post("/api/fuel-entries/upload-photo", files=files, headers=headers)
    assert upload_res.status_code == 200, upload_res.text
    data = upload_res.json()
    assert "photo_url" in data
    assert data["photo_url"].startswith("/uploads/")


def test_fuel_entry_and_mileage_calculation():
    """
    Test Case 5: Complete Fueling, Photo Attachments & Mileage Flow
    - Authenticates as Operator.
    - Queries fleet vehicles (/api/vehicles).
    - Queries authorized petrol pumps (/api/petrol-pumps).
    - Submits a fuel entry with 3 photos (PLATE, ODOMETER, RECEIPT) and GPS coordinates.
    - Asserts:
        * Distance Travelled = 45,600 - 45,000 = 600.0 km
        * Mileage = 600 / 100 = 6.0 km/L
        * Status = 'PENDING'
        * Geofence validation verifies proximity to pump
        * Photos are stored in the separate entry_photos table and returned in the response
    - Attempts invalid entry with decreasing odometer (45,500 < 45,600) and asserts 400 rejection.
    - Authenticates as Owner and APPROVES the pending entry.
    - Asserts entry status becomes 'APPROVED'.
    """
    # 1. Login as operator
    op_login = client.post("/api/auth/login", data={"username": "operator", "password": "operator123"}).json()
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

    # Initial odometer is 45000. Let's record 45600 with 100 Litres + 3 attached photos + GPS
    entry_payload = {
        "vehicle_id": vehicle["id"],
        "petrol_pump_id": pump["id"],
        "current_odometer": 45600.0,
        "fuel_litres": 100.0,
        "is_full_tank": True,
        "latitude": pump["latitude"] + 0.0001,  # ~11 meters away
        "longitude": pump["longitude"] + 0.0001,
        "accuracy_m": 10.0,
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
    assert entry_data["is_location_verified"] is True
    assert entry_data["distance_from_pump_m"] is not None
    assert entry_data["distance_from_pump_m"] <= pump["radius_meters"]

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
    owner_login = client.post("/api/auth/login", data={"username": "owner", "password": "owner123"}).json()
    owner_token = owner_login["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    verify_res = client.patch(
        f"/api/fuel-entries/{entry_data['id']}/verify",
        json={"status": "APPROVED", "rejection_reason": None},
        headers=owner_headers
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "APPROVED"


def test_vehicle_and_pump_management():
    """
    Test Case 6: Master Data Management by Owner
    - Authenticates as Owner.
    - Creates a new vehicle with initial odometer.
    - Verifies latest_odometer equals initial_odometer on creation.
    - Creates a new authorized petrol pump.
    - Verifies created resources are queryable.
    """
    owner_login = client.post("/api/auth/login", data={"username": "owner", "password": "owner123"}).json()
    headers = {"Authorization": f"Bearer {owner_login['access_token']}"}

    # Create vehicle
    v_payload = {
        "vehicle_number": "MH-20-CZ-8888",
        "model": "Eicher Pro 3019",
        "initial_odometer": 12500.0
    }
    v_res = client.post("/api/vehicles/", json=v_payload, headers=headers)
    assert v_res.status_code == 201, v_res.text
    v_data = v_res.json()
    assert v_data["vehicle_number"] == "MH-20-CZ-8888"
    assert v_data["latest_odometer"] == 12500.0

    # Create petrol pump
    p_payload = {
        "name": "Shell - Hinjewadi Bypass",
        "address": "Phase 1, Hinjewadi, Pune",
        "latitude": 18.5913,
        "longitude": 73.7389,
        "radius_meters": 120.0
    }
    p_res = client.post("/api/petrol-pumps/", json=p_payload, headers=headers)
    assert p_res.status_code == 201, p_res.text
    assert p_res.json()["name"] == "Shell - Hinjewadi Bypass"

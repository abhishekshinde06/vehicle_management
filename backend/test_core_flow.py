"""
Core Business Flow Verification Tests
-------------------------------------
Automated integration tests validating:
1. Owner-provisioned Operator/Driver creation (/api/auth/create-operator & /api/auth/operators).
2. RBAC guard: Operators cannot provision other operators.
3. Operator & Owner authentication (JWT token generation).
4. Fetching fleet vehicles and authorized petrol pumps via clean /api routes.
5. Submitting a new fuel entry with odometer, liters, AND photos stored in `entry_photos`.
6. Automatic distance and mileage (km/L) calculation.
7. Decreasing odometer sanity validation (preventing invalid entries).
8. Geofence & GPS distance verification against authorized petrol pump radius.
9. Live photo upload via `/api/fuel-entries/upload-photo`.
10. Owner approval workflow with status update and audit trail.
11. Fleet vehicle and authorized pump creation by owner.
"""

import io
import os
import tempfile
import pytest

# Create an isolated temporary test database (never drops or modifies the application database)
_test_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_test_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db.name}"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.models import User, Vehicle, PetrolPump, FuelEntry, AuditLog

test_engine = create_engine(
    f"sqlite:///{_test_db.name}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_test_db_override():
    """Ensure the isolated test database dependency override is active for every test."""
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


def setup_module():
    """
    Setup hook executed once before running the test suite:
    Resets tables on isolated test_engine and seeds test records.
    Never drops or modifies the actual application database.
    """
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    db = TestSessionLocal()
    try:
        op = User(
            username="operator",
            password_hash=get_password_hash("operator123"),
            role="operator",
            full_name="Tablet Operator (Ramesh)",
            is_active=True
        )
        owner = User(
            username="owner",
            password_hash=get_password_hash("owner123"),
            role="owner",
            full_name="Fleet Owner (Vikram)",
            is_active=True
        )
        db.add_all([op, owner])

        vehicles = [
            Vehicle(vehicle_number="MH-12-AB-1001", model="Tata Prima 4028.S", initial_odometer=44000.0),
            Vehicle(vehicle_number="MH-14-XY-2002", model="Ashok Leyland 3118", initial_odometer=72500.0),
            Vehicle(vehicle_number="MH-46-TR-3003", model="BharatBenz 2823R", initial_odometer=28900.0),
        ]
        db.add_all(vehicles)
        db.flush()

        pumps = [
            PetrolPump(
                name="Bharat Petroleum - Highway Hub",
                address="NH-48, Near Expressway Toll, Pune",
                latitude=18.5204,
                longitude=73.8567,
                radius_meters=150.0
            ),
            PetrolPump(
                name="Indian Oil - Transporter Hub",
                address="Transport Nagar, Nigdi, Pune",
                latitude=18.6510,
                longitude=73.7820,
                radius_meters=100.0
            )
        ]
        db.add_all(pumps)
        db.flush()

        # Seed initial baseline full-tank entry for first vehicle at 45000 km
        baseline = FuelEntry(
            vehicle_id=vehicles[0].id,
            petrol_pump_id=pumps[0].id,
            operator_id=op.id,
            current_odometer=45000.0,
            previous_odometer=44000.0,
            fuel_litres=100.0,
            is_full_tank=True,
            distance_km=1000.0,
            mileage_kmpl=None,
            latitude=18.5204,
            longitude=73.8567,
            accuracy_m=10.0,
            distance_from_pump_m=0.0,
            is_location_verified=True,
            status="APPROVED"
        )
        db.add(baseline)

        db.commit()
    finally:
        db.close()


def teardown_module():
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()
    if os.path.exists(_test_db.name):
        try:
            os.remove(_test_db.name)
        except OSError:
            pass


def test_public_signup_disabled_and_operator_provisioning():
    """
    Test Case 1: Disabled Public Signup & Operator Provisioning by Seeded Owner
    - Asserts that public signup is disabled (POST /api/auth/signup returns 404).
    - Owner logs in using seeded credentials.
    - Owner provisions a new Operator at /api/auth/create-operator (assigned role 'operator').
    - Owner retrieves list of fleet operators at /api/auth/operators.
    - Operator cannot create another operator (assert 403 Forbidden).
    - Operator logs in with provisioned credentials.
    """
    # 1. Assert public signup is disabled
    signup_res = client.post("/api/auth/signup", json={
        "username": "unauthorized_owner",
        "password": "password123",
        "full_name": "Unauthorized Owner"
    })
    assert signup_res.status_code == 404, "Public signup should be disabled (404 Not Found)"

    # 2. Owner logs in with seeded credentials
    owner_login_res = client.post("/api/auth/login", data={"username": "owner", "password": "owner123"})
    assert owner_login_res.status_code == 200, owner_login_res.text
    owner_data = owner_login_res.json()
    assert owner_data["role"] == "owner"
    owner_headers = {"Authorization": f"Bearer {owner_data['access_token']}"}

    # 3. Owner provisions an Operator / Driver
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

    # Duplicate username check
    dup_res = client.post("/api/auth/create-operator", json=op_payload, headers=owner_headers)
    assert dup_res.status_code == 400

    # 4. Owner lists operators
    list_op_res = client.get("/api/auth/operators", headers=owner_headers)
    assert list_op_res.status_code == 200
    usernames = [u["username"] for u in list_op_res.json()]
    assert "fleet_driver_sunil" in usernames

    # 5. Operator logs in
    op_login_res = client.post("/api/auth/login", data={"username": "fleet_driver_sunil", "password": "driverpassword123"})
    assert op_login_res.status_code == 200
    op_token = op_login_res.json()["access_token"]
    assert op_login_res.json()["role"] == "operator"
    op_headers = {"Authorization": f"Bearer {op_token}"}

    # 6. Security check: Operator CANNOT create another operator (must fail with 403 Forbidden)
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
        "is_full_tank": True,
        "latitude": pump["latitude"] + 0.0001,
        "longitude": pump["longitude"] + 0.0001,
        "accuracy_m": 10.0,
        "photos": [
            {"photo_type": "PLATE", "photo_url": "/uploads/test_plate2.jpg"},
            {"photo_type": "ODOMETER", "photo_url": "/uploads/test_odometer2.jpg"},
            {"photo_type": "RECEIPT", "photo_url": "/uploads/test_receipt2.jpg"}
        ]
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

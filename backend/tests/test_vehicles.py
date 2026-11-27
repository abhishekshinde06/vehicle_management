"""
Vehicle Route Tests
-------------------
Tests for /api/vehicles endpoints:

  1. test_list_vehicles_unauthenticated        — GET / without token -> 401
  2. test_list_vehicles_as_operator            — GET / as operator returns active vehicles (200)
  3. test_list_vehicles_as_owner               — GET / as owner returns active vehicles (200)
  4. test_list_vehicles_latest_odometer_fallback — If no fuel entries, latest_odometer == initial_odometer
  5. test_list_vehicles_latest_odometer_calculated — Returns latest entry odometer, ignores REJECTED entries
  6. test_list_vehicles_excludes_inactive      — Inactive vehicles are omitted from the list
  7. test_create_vehicle_as_owner              — POST / as owner successfully creates vehicle (201)
  8. test_create_vehicle_duplicate_number      — POST / with existing vehicle_number -> 400
  9. test_create_vehicle_as_operator_forbidden — POST / as operator -> 403 Forbidden
  10. test_create_vehicle_unauthenticated      — POST / without token -> 401
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.petrol_pump import PetrolPump
from app.models.fuel_entry import FuelEntry

# In-memory SQLite DB for vehicle tests
TEST_DATABASE_URL = "sqlite:///./test_vehicles.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="module")
def db():
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="module")
def client(db):
    # Seed users
    owner = User(
        id="owner-uuid-1",
        username="vehicle_owner",
        password_hash=get_password_hash("ownerpass"),
        role="owner",
        full_name="Vehicle Fleet Owner",
        is_active=True,
    )
    operator = User(
        id="operator-uuid-1",
        username="vehicle_operator",
        password_hash=get_password_hash("operatorpass"),
        role="operator",
        full_name="Vehicle Operator",
        is_active=True,
    )
    db.add_all([owner, operator])
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def owner_headers():
    token = create_access_token(subject="owner-uuid-1", role="owner")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def operator_headers():
    token = create_access_token(subject="operator-uuid-1", role="operator")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestListVehicles:

    def test_list_vehicles_unauthenticated(self, client):
        """Unauthenticated requests must be rejected with 401."""
        res = client.get("/api/vehicles/")
        assert res.status_code == 401

    def test_list_vehicles_as_operator(self, client, operator_headers):
        """Operators have read access to the vehicle list."""
        res = client.get("/api/vehicles/", headers=operator_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_vehicles_as_owner(self, client, owner_headers):
        """Owners have read access to the vehicle list."""
        res = client.get("/api/vehicles/", headers=owner_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_vehicles_latest_odometer_fallback(self, client, db, operator_headers):
        """When vehicle has no fuel entries, latest_odometer should equal initial_odometer."""
        v = Vehicle(
            id="v-new-1",
            vehicle_number="MH-12-NEW-01",
            model="Tata 407",
            initial_odometer=10000.0,
            is_active=True
        )
        db.add(v)
        db.commit()

        res = client.get("/api/vehicles/", headers=operator_headers)
        assert res.status_code == 200
        vehicle_data = next((item for item in res.json() if item["id"] == "v-new-1"), None)
        assert vehicle_data is not None
        assert vehicle_data["initial_odometer"] == 10000.0
        assert vehicle_data["latest_odometer"] == 10000.0

    def test_list_vehicles_latest_odometer_with_entries(self, client, db, operator_headers):
        """latest_odometer reflects the most recent approved/pending entry, ignoring rejected."""
        # 1. Create vehicle
        v = Vehicle(
            id="v-fueled-1",
            vehicle_number="MH-12-FUEL-02",
            model="Ashok Leyland",
            initial_odometer=20000.0,
            is_active=True
        )
        # 2. Petrol pump required for FuelEntry FK
        pump = PetrolPump(
            id="pump-test-1",
            name="Test Pump",
            latitude=18.5,
            longitude=73.8,
            radius_meters=100.0,
            is_active=True
        )
        db.add_all([v, pump])
        db.commit()

        # 3. Add approved fuel entry at 20500 km
        entry_approved = FuelEntry(
            id="entry-1",
            vehicle_id=v.id,
            petrol_pump_id=pump.id,
            operator_id="operator-uuid-1",
            current_odometer=20500.0,
            previous_odometer=20000.0,
            fuel_litres=50.0,
            status="APPROVED"
        )
        # 4. Add newer rejected entry at 99999 km (should be ignored by query)
        entry_rejected = FuelEntry(
            id="entry-2",
            vehicle_id=v.id,
            petrol_pump_id=pump.id,
            operator_id="operator-uuid-1",
            current_odometer=99999.0,
            previous_odometer=20500.0,
            fuel_litres=50.0,
            status="REJECTED"
        )
        db.add_all([entry_approved, entry_rejected])
        db.commit()

        res = client.get("/api/vehicles/", headers=operator_headers)
        assert res.status_code == 200
        data = next((item for item in res.json() if item["id"] == "v-fueled-1"), None)
        assert data is not None
        # Must reflect the approved entry (20500.0), NOT initial (20000.0) or rejected (99999.0)
        assert data["latest_odometer"] == 20500.0

    def test_list_vehicles_excludes_inactive(self, client, db, operator_headers):
        """Vehicles with is_active=False must be excluded from listing."""
        v_inactive = Vehicle(
            id="v-inactive-1",
            vehicle_number="MH-12-INACTIVE",
            initial_odometer=5000.0,
            is_active=False
        )
        db.add(v_inactive)
        db.commit()

        res = client.get("/api/vehicles/", headers=operator_headers)
        assert res.status_code == 200
        ids = [item["id"] for item in res.json()]
        assert "v-inactive-1" not in ids


class TestCreateVehicle:

    def test_create_vehicle_as_owner(self, client, owner_headers):
        """Owner can successfully register a new vehicle."""
        payload = {
            "vehicle_number": "MH-14-AA-9999",
            "model": "BharatBenz 2823R",
            "initial_odometer": 35000.0
        }
        res = client.post("/api/vehicles/", json=payload, headers=owner_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["vehicle_number"] == "MH-14-AA-9999"
        assert data["model"] == "BharatBenz 2823R"
        assert data["initial_odometer"] == 35000.0
        assert data["latest_odometer"] == 35000.0
        assert data["is_active"] is True
        assert "id" in data

    def test_create_vehicle_duplicate_number(self, client, owner_headers):
        """Attempting to create a duplicate vehicle number returns 400 Bad Request."""
        payload = {
            "vehicle_number": "MH-14-AA-9999",
            "model": "Another Model",
            "initial_odometer": 1000.0
        }
        res = client.post("/api/vehicles/", json=payload, headers=owner_headers)
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"].lower()

    def test_create_vehicle_as_operator_forbidden(self, client, operator_headers):
        """Operators cannot create vehicles; must return 403 Forbidden."""
        payload = {
            "vehicle_number": "MH-14-OP-0001",
            "initial_odometer": 1000.0
        }
        res = client.post("/api/vehicles/", json=payload, headers=operator_headers)
        assert res.status_code == 403

    def test_create_vehicle_unauthenticated(self, client):
        """Unauthenticated requests must return 401 Unauthorized."""
        payload = {
            "vehicle_number": "MH-14-AB-0002",
            "initial_odometer": 0.0
        }
        res = client.post("/api/vehicles/", json=payload)
        assert res.status_code == 401

    def test_create_vehicle_invalid_number_rejected(self, client, owner_headers):
        """Invalid vehicle numbers (arbitrary text, numbers only, blanks) must return 422."""
        for bad_number in ["   ", "12345", "hello world", "NOT-A-VEHICLE", "@@@"]:
            res = client.post(
                "/api/vehicles/",
                json={"vehicle_number": bad_number, "initial_odometer": 0.0},
                headers=owner_headers,
            )
            assert res.status_code == 422, f"Expected 422 for {bad_number!r}, got {res.status_code}"

    def test_create_vehicle_normalizes_lowercase(self, client, owner_headers):
        """Lowercase valid vehicle number is normalized to uppercase."""
        res = client.post(
            "/api/vehicles/",
            json={"vehicle_number": "mh-12-cd-4567", "initial_odometer": 100.0},
            headers=owner_headers,
        )
        assert res.status_code == 201
        assert res.json()["vehicle_number"] == "MH-12-CD-4567"

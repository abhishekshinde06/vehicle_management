"""
Petrol Pump Route Tests
-----------------------
Tests for /api/petrol-pumps endpoints:

  1. test_list_petrol_pumps_unauthenticated     — GET / without token -> 401
  2. test_list_petrol_pumps_as_operator         — GET / as operator returns pumps (200)
  3. test_list_petrol_pumps_as_owner            — GET / as owner returns pumps (200)
  4. test_create_petrol_pump_as_owner           — POST / as owner successfully creates pump (201)
  5. test_create_petrol_pump_duplicate_name     — POST / with duplicate name (case-insensitive) -> 400
  6. test_create_petrol_pump_duplicate_coords   — POST / with duplicate GPS coords -> 400
  7. test_create_petrol_pump_as_operator_forbidden — POST / as operator -> 403 Forbidden
  8. test_create_petrol_pump_unauthenticated   — POST / without token -> 401
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.models.user import User
from app.models.petrol_pump import PetrolPump

TEST_DATABASE_URL = "sqlite:///./test_petrol_pumps.db"
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
    owner = User(
        id="owner-pump-test-1",
        username="pump_owner",
        password_hash=get_password_hash("ownerpass"),
        role="owner",
        full_name="Pump Test Owner",
        is_active=True,
    )
    operator = User(
        id="operator-pump-test-1",
        username="pump_operator",
        password_hash=get_password_hash("operatorpass"),
        role="operator",
        full_name="Pump Test Operator",
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
    token = create_access_token(subject="owner-pump-test-1", role="owner")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def operator_headers():
    token = create_access_token(subject="operator-pump-test-1", role="operator")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestListPetrolPumps:

    def test_list_petrol_pumps_unauthenticated(self, client):
        """Unauthenticated requests must return 401."""
        res = client.get("/api/petrol-pumps/")
        assert res.status_code == 401

    def test_list_petrol_pumps_as_operator(self, client, operator_headers):
        """Operators have read access to the authorized pumps list."""
        res = client.get("/api/petrol-pumps/", headers=operator_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_petrol_pumps_as_owner(self, client, owner_headers):
        """Owners have read access to the authorized pumps list."""
        res = client.get("/api/petrol-pumps/", headers=owner_headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)


class TestCreatePetrolPump:

    def test_create_petrol_pump_as_owner(self, client, owner_headers):
        """Owner can successfully register a new authorized petrol pump."""
        payload = {
            "name": "Bharat Petroleum Expressway Hub",
            "address": "NH-48, Urse Toll Plaza, Pune",
            "latitude": 18.7305,
            "longitude": 73.6552,
            "radius_meters": 150.0
        }
        res = client.post("/api/petrol-pumps/", json=payload, headers=owner_headers)
        assert res.status_code == 201
        data = res.json()
        assert data["name"] == "Bharat Petroleum Expressway Hub"
        assert data["latitude"] == 18.7305
        assert data["longitude"] == 73.6552
        assert data["radius_meters"] == 150.0
        assert data["is_active"] is True
        assert "id" in data

    def test_create_petrol_pump_duplicate_name(self, client, owner_headers):
        """Attempting to register a pump with an existing name (case-insensitive) returns 400."""
        payload = {
            "name": "bharat petroleum expressway hub",  # lowercase duplicate
            "address": "Different address",
            "latitude": 19.1234,
            "longitude": 74.5678,
            "radius_meters": 100.0
        }
        res = client.post("/api/petrol-pumps/", json=payload, headers=owner_headers)
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"].lower()

    def test_create_petrol_pump_duplicate_coords(self, client, owner_headers):
        """Attempting to register a pump at the exact same GPS coordinates returns 400."""
        payload = {
            "name": "Shell Petrol Station",
            "address": "Exact same spot as first pump",
            "latitude": 18.7305,   # Same latitude as first pump
            "longitude": 73.6552,  # Same longitude as first pump
            "radius_meters": 100.0
        }
        res = client.post("/api/petrol-pumps/", json=payload, headers=owner_headers)
        assert res.status_code == 400
        assert "coordinates" in res.json()["detail"].lower()

    def test_create_petrol_pump_as_operator_forbidden(self, client, operator_headers):
        """Operators cannot register petrol pumps; returns 403 Forbidden."""
        payload = {
            "name": "Unauthorized Operator Pump",
            "latitude": 18.1111,
            "longitude": 73.2222,
            "radius_meters": 100.0
        }
        res = client.post("/api/petrol-pumps/", json=payload, headers=operator_headers)
        assert res.status_code == 403

    def test_create_petrol_pump_unauthenticated(self, client):
        """Unauthenticated POST requests return 401."""
        payload = {
            "name": "No Auth Pump",
            "latitude": 18.0000,
            "longitude": 73.0000,
            "radius_meters": 100.0
        }
        res = client.post("/api/petrol-pumps/", json=payload)
        assert res.status_code == 401

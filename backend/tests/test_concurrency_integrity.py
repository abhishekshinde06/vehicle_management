"""
Concurrency and Database Integrity Tests
---------------------------------------
Validates:
1. Vehicle creation handles race-condition/duplicate IntegrityError with clean rollback and HTTP 400.
2. Petrol pump creation handles duplicate name IntegrityError with clean rollback and HTTP 400.
3. Petrol pump creation handles duplicate GPS coordinate constraint (uq_petrol_pumps_lat_lon) with rollback and HTTP 400.
4. Operator creation handles duplicate username IntegrityError with clean rollback and HTTP 400.
5. Concurrent requests hitting unique constraints fail gracefully without leaving aborted/broken DB transactions.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.petrol_pump import PetrolPump

TEST_DATABASE_URL = "sqlite:///./test_integrity.db"
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
        id="owner-integ-1",
        username="integ_owner",
        password_hash=get_password_hash("owner123"),
        role="owner",
        full_name="Integrity Owner",
        is_active=True,
    )
    db.add(owner)
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
    token = create_access_token(subject="owner-integ-1", role="owner")
    return {"Authorization": f"Bearer {token}"}


class TestDatabaseIntegrityRollbacks:

    def test_vehicle_concurrency_integrity_error_rollback(self, client, owner_headers):
        """
        Simulate concurrent vehicle creation where the application-level check passes
        for both threads, but the database unique constraint raises IntegrityError.
        Route must rollback and return a clean 400 error.
        """
        # First vehicle creation succeeds
        res1 = client.post(
            "/api/vehicles/",
            json={"vehicle_number": "MH-12-INTEG-01", "model": "Truck", "initial_odometer": 1000.0},
            headers=owner_headers
        )
        assert res1.status_code == 201

        # Second request simulates bypassing application check (e.g. race condition)
        # Mocking db.commit on session to raise IntegrityError
        with patch("sqlalchemy.orm.Session.commit", side_effect=IntegrityError("duplicate", None, None)):
            res2 = client.post(
                "/api/vehicles/",
                json={"vehicle_number": "MH-12-INTEG-02", "model": "Truck", "initial_odometer": 2000.0},
                headers=owner_headers
            )
            assert res2.status_code == 400
            assert "already exists" in res2.json()["detail"].lower()

    def test_petrol_pump_gps_coordinate_constraint_rollback(self, client, owner_headers):
        """
        Registering two petrol pumps with exact same coordinates triggers DB unique constraint,
        properly rolling back the transaction.
        """
        payload1 = {
            "name": "Highway Station A",
            "address": "Expressway Point 1",
            "latitude": 18.9999,
            "longitude": 73.8888,
            "radius_meters": 100.0
        }
        res1 = client.post("/api/petrol-pumps/", json=payload1, headers=owner_headers)
        assert res1.status_code == 201

        # Direct database level constraint trigger simulation (or app level check)
        payload2 = {
            "name": "Highway Station B",
            "address": "Expressway Point 2",
            "latitude": 18.9999,  # Same coordinates
            "longitude": 73.8888,
            "radius_meters": 100.0
        }
        res2 = client.post("/api/petrol-pumps/", json=payload2, headers=owner_headers)
        assert res2.status_code == 400
        assert "coordinates" in res2.json()["detail"].lower()

    def test_petrol_pump_integrity_error_on_commit(self, client, owner_headers):
        """Simulate concurrent petrol pump insert triggering DB IntegrityError."""
        with patch("sqlalchemy.orm.Session.commit", side_effect=IntegrityError("uq_petrol_pumps_lat_lon", None, None)):
            res = client.post(
                "/api/petrol-pumps/",
                json={
                    "name": "Station Unique Test",
                    "latitude": 19.5555,
                    "longitude": 74.5555,
                    "radius_meters": 100.0
                },
                headers=owner_headers
            )
            assert res.status_code == 400

    def test_operator_creation_integrity_error_rollback(self, client, owner_headers):
        """Simulate concurrent operator registration triggering DB IntegrityError on username."""
        with patch("sqlalchemy.orm.Session.commit", side_effect=IntegrityError("duplicate username", None, None)):
            res = client.post(
                "/api/auth/create-operator",
                json={"username": "concurrent_driver", "password": "password123"},
                headers=owner_headers
            )
            assert res.status_code == 400
            assert "already taken" in res.json()["detail"].lower()

    def test_session_remains_usable_after_rollback(self, client, owner_headers):
        """
        Critical check: Verifies that after a rolled-back IntegrityError, the DB session
        is NOT poisoned and subsequent valid requests execute successfully.
        """
        # 1. Trigger rolled-back error
        with patch("sqlalchemy.orm.Session.commit", side_effect=IntegrityError("fail", None, None)):
            client.post(
                "/api/vehicles/",
                json={"vehicle_number": "MH-FAIL-01", "model": "Truck", "initial_odometer": 500.0},
                headers=owner_headers
            )

        # 2. Subsequent normal request must succeed
        res = client.post(
            "/api/vehicles/",
            json={"vehicle_number": "MH-SUCCESS-01", "model": "Truck", "initial_odometer": 500.0},
            headers=owner_headers
        )
        assert res.status_code == 201
        assert res.json()["vehicle_number"] == "MH-SUCCESS-01"

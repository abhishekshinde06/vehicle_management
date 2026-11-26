import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from app.main import app
from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.models.user import User
from app.models.petrol_pump import PetrolPump


@pytest.fixture
def session_factory(tmp_path):
    db_path = tmp_path / "test_petrol_pumps.db"

    test_db_url = os.getenv("PUMP_TEST_DATABASE_URL")

    if test_db_url:
        engine = create_engine(test_db_url)

        assert engine.dialect.name == "postgresql"
        assert engine.url.database == "fuel_tracker_pump_test"

        Base.metadata.drop_all(bind=engine)
    else:
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False}
        )

    Base.metadata.create_all(bind=engine)


    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

    with SessionLocal() as db:
        db.add_all([
            User(
                id="owner-pump-test-1",
                username="pump_owner",
                password_hash=get_password_hash("ownerpass"),
                role="owner",
                full_name="Pump Test Owner",
                is_active=True,
            ),
            User(
                id="operator-pump-test-1",
                username="pump_operator",
                password_hash=get_password_hash("operatorpass"),
                role="operator",
                full_name="Pump Test Operator",
                is_active=True,
            )
        ])

        db.add(
            PetrolPump(
                name="Existing Petrol Pump",
                latitude=18.7305,
                longitude=73.6552,
                radius_meters=100.0,
                is_active=True
            )
        )

        db.commit()

    try:
        yield SessionLocal
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(session_factory):

    def override_get_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def owner_headers():
    token = create_access_token(
        subject="owner-pump-test-1",
        role="owner"
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def operator_headers():
    token = create_access_token(
        subject="operator-pump-test-1",
        role="operator"
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def payload():
    return {
        "name": "New Petrol Pump",
        "address": "Test Address",
        "latitude": 23.2599,
        "longitude": 77.4126,
        "radius_meters": 100.0
    }


class TestListPetrolPumps:

    def test_list_unauthenticated(self, client):
        res = client.get("/api/petrol-pumps/")
        assert res.status_code == 401

    def test_list_as_operator(self, client, operator_headers):
        res = client.get(
            "/api/petrol-pumps/",
            headers=operator_headers
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_list_as_owner(self, client, owner_headers):
        res = client.get(
            "/api/petrol-pumps/",
            headers=owner_headers
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)


class TestCreatePetrolPump:

    def test_create_as_owner(
        self, client, owner_headers, payload
    ):
        res = client.post(
            "/api/petrol-pumps/",
            json=payload,
            headers=owner_headers
        )

        assert res.status_code == 201
        assert res.json()["name"] == payload["name"]
        assert res.json()["is_active"] is True
        assert "id" in res.json()

    def test_duplicate_name(
        self, client, owner_headers, payload
    ):
        payload["name"] = "Existing Petrol Pump"

        res = client.post(
            "/api/petrol-pumps/",
            json=payload,
            headers=owner_headers
        )

        assert res.status_code == 400

    def test_duplicate_name_case_insensitive(
        self, client, owner_headers, payload
    ):
        payload["name"] = "  existing petrol pump  "

        res = client.post(
            "/api/petrol-pumps/",
            json=payload,
            headers=owner_headers
        )

        assert res.status_code == 400

    def test_duplicate_coordinates(
        self, client, owner_headers, payload
    ):
        payload["latitude"] = 18.7305
        payload["longitude"] = 73.6552

        res = client.post(
            "/api/petrol-pumps/",
            json=payload,
            headers=owner_headers
        )

        assert res.status_code == 400

    def test_nearby_pump_allowed(
        self, client, owner_headers, payload
    ):
        payload["latitude"] = 18.7306
        payload["longitude"] = 73.6552

        res = client.post(
            "/api/petrol-pumps/",
            json=payload,
            headers=owner_headers
        )

        assert res.status_code == 201

    def test_operator_forbidden(
        self, client, operator_headers, payload
    ):
        res = client.post(
            "/api/petrol-pumps/",
            json=payload,
            headers=operator_headers
        )

        assert res.status_code == 403

    def test_create_unauthenticated(
        self, client, payload
    ):
        res = client.post(
            "/api/petrol-pumps/",
            json=payload
        )

        assert res.status_code == 401

    @pytest.mark.parametrize("field,value", [
        ("name", ""),
        ("name", "   "),
        ("latitude", 95),
        ("latitude", -95),
        ("longitude", 190),
        ("longitude", -190),
        ("radius_meters", 0),
        ("radius_meters", -100),
    ])
    def test_invalid_pump_data(
        self, client, owner_headers, payload, field, value
    ):
        payload[field] = value

        res = client.post(
            "/api/petrol-pumps/",
            json=payload,
            headers=owner_headers
        )

        assert res.status_code == 422
    @pytest.mark.parametrize("duplicate_type", ["name", "coordinates"])
    def test_concurrent_duplicate_registration(
        self, client, owner_headers, payload,
        session_factory, duplicate_type
    ):
        first = payload.copy()
        second = payload.copy()

        if duplicate_type == "name":
            second["name"] = first["name"].upper()
            second["latitude"] += 0.01
        else:
            second["name"] = "Another Petrol Pump"

        barrier = Barrier(2)

        def register(data):
            barrier.wait(timeout=10)

            return client.post(
                "/api/petrol-pumps/",
                json=data,
                headers=owner_headers
            ).status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(register, [first, second]))

        assert sorted(results) == [201, 400]

        with session_factory() as db:
            assert db.query(PetrolPump).count() == 2
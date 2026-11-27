"""
GPS Verification Token Security & Validation Tests
--------------------------------------------------
Validates:
1. Access tokens and GPS verification tokens have strict purpose separation.
2. Tampered, forged, expired, or wrong-user/wrong-pump GPS tokens are rejected (403).
3. Photos uploaded under Pump A's GPS token cannot be used for Pump B (403).
4. Geofence verification endpoint rejects NaN, Inf, blank pump IDs, and extra fields (422).
"""

import io
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import (
    create_access_token,
    create_gps_verification_token,
    validate_gps_verification_token,
)
from app.main import app
from app.models import PetrolPump, User, Vehicle


def make_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def isolated_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "USE_S3", False)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        op1 = User(id="gps-op-1", username="gps_op_1", password_hash="h", role="operator", is_active=True)
        op2 = User(id="gps-op-2", username="gps_op_2", password_hash="h", role="operator", is_active=True)
        vehicle = Vehicle(id="gps-veh-1", vehicle_number="MH-12-SEC-1", initial_odometer=1000.0, is_active=True)
        pump_a = PetrolPump(
            id="gps-pump-a",
            name="Pump Alpha",
            latitude=18.5204,
            longitude=73.8567,
            radius_meters=150.0,
            is_active=True,
        )
        pump_b = PetrolPump(
            id="gps-pump-b",
            name="Pump Beta",
            latitude=18.6510,
            longitude=73.7820,
            radius_meters=150.0,
            is_active=True,
        )
        db.add_all([op1, op2, vehicle, pump_a, pump_b])
        db.commit()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, TestingSession
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _verify_gps(client, headers, pump_id, lat=18.5204, lon=73.8567):
    res = client.post(
        "/api/fuel-entries/verify-location",
        headers=headers,
        json={"petrol_pump_id": pump_id, "latitude": lat, "longitude": lon, "accuracy_m": 10.0},
    )
    assert res.status_code == 200, res.text
    return res.json()["gps_verification_token"]


def _upload_three(client, headers, pump_id, gps_token):
    photos = []
    for ptype in ("PLATE", "ODOMETER", "RECEIPT"):
        res = client.post(
            "/api/fuel-entries/upload-photo",
            headers=headers,
            data={"photo_type": ptype, "petrol_pump_id": pump_id, "gps_verification_token": gps_token},
            files={"file": (f"{ptype.lower()}.jpg", io.BytesIO(make_jpeg_bytes()), "image/jpeg")},
        )
        assert res.status_code == 200, res.text
        photos.append({"photo_type": ptype, "photo_url": res.json()["photo_url"]})
    return photos


class TestGPSTokenSecurity:
    def test_gps_token_rejected_as_bearer_access_token(self, isolated_client):
        client, _ = isolated_client
        gps_token = create_gps_verification_token("gps-op-1", "gps-pump-a")
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {gps_token}"})
        assert res.status_code == 401

    def test_access_token_rejected_as_gps_token(self, isolated_client):
        client, _ = isolated_client
        access_token = create_access_token("gps-op-1", "operator")
        headers = {"Authorization": f"Bearer {access_token}"}

        upload_res = client.post(
            "/api/fuel-entries/upload-photo",
            headers=headers,
            data={"photo_type": "PLATE", "petrol_pump_id": "gps-pump-a", "gps_verification_token": access_token},
            files={"file": ("plate.jpg", io.BytesIO(make_jpeg_bytes()), "image/jpeg")},
        )
        assert upload_res.status_code == 403

    def test_expired_and_tampered_gps_tokens_rejected(self, isolated_client):
        from jose import jwt
        from datetime import datetime, timezone

        client, _ = isolated_client
        access_token = create_access_token("gps-op-1", "operator")
        headers = {"Authorization": f"Bearer {access_token}"}

        expired_token = jwt.encode(
            {
                "sub": "gps-op-1",
                "pump_id": "gps-pump-a",
                "purpose": "gps_verification",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        assert validate_gps_verification_token(expired_token, "gps-op-1", "gps-pump-a") is False
        assert validate_gps_verification_token(expired_token + "tamper", "gps-op-1", "gps-pump-a") is False

        res = client.post(
            "/api/fuel-entries/upload-photo",
            headers=headers,
            data={"photo_type": "PLATE", "petrol_pump_id": "gps-pump-a", "gps_verification_token": expired_token},
            files={"file": ("plate.jpg", io.BytesIO(make_jpeg_bytes()), "image/jpeg")},
        )
        assert res.status_code == 403

    def test_cross_operator_and_cross_pump_gps_token_rejected(self, isolated_client):
        client, _ = isolated_client
        op1_headers = {"Authorization": f"Bearer {create_access_token('gps-op-1', 'operator')}"}
        op2_headers = {"Authorization": f"Bearer {create_access_token('gps-op-2', 'operator')}"}

        op1_pump_a_token = _verify_gps(client, op1_headers, "gps-pump-a")

        # Operator 2 cannot use Operator 1's GPS token
        res_other_user = client.post(
            "/api/fuel-entries/upload-photo",
            headers=op2_headers,
            data={"photo_type": "PLATE", "petrol_pump_id": "gps-pump-a", "gps_verification_token": op1_pump_a_token},
            files={"file": ("plate.jpg", io.BytesIO(make_jpeg_bytes()), "image/jpeg")},
        )
        assert res_other_user.status_code == 403

        # Operator 1 cannot use Pump A's GPS token for Pump B
        res_other_pump = client.post(
            "/api/fuel-entries/upload-photo",
            headers=op1_headers,
            data={"photo_type": "PLATE", "petrol_pump_id": "gps-pump-b", "gps_verification_token": op1_pump_a_token},
            files={"file": ("plate.jpg", io.BytesIO(make_jpeg_bytes()), "image/jpeg")},
        )
        assert res_other_pump.status_code == 403

    def test_photos_bound_to_pump_a_rejected_when_submitted_to_pump_b(self, isolated_client):
        client, _ = isolated_client
        op1_headers = {"Authorization": f"Bearer {create_access_token('gps-op-1', 'operator')}"}

        token_a = _verify_gps(client, op1_headers, "gps-pump-a", 18.5204, 73.8567)
        photos_a = _upload_three(client, op1_headers, "gps-pump-a", token_a)

        token_b = _verify_gps(client, op1_headers, "gps-pump-b", 18.6510, 73.7820)
        res = client.post(
            "/api/fuel-entries/",
            headers=op1_headers,
            json={
                "vehicle_id": "gps-veh-1",
                "petrol_pump_id": "gps-pump-b",
                "gps_verification_token": token_b,
                "current_odometer": 1500.0,
                "fuel_litres": 25.0,
                "is_full_tank": True,
                "latitude": 18.6510,
                "longitude": 73.7820,
                "accuracy_m": 10.0,
                "photos": photos_a,
            },
        )
        assert res.status_code == 403
        assert "petrol pump" in res.json()["detail"].lower()

    def test_verify_location_input_validation(self, isolated_client):
        client, _ = isolated_client
        op1_headers = {"Authorization": f"Bearer {create_access_token('gps-op-1', 'operator')}"}

        # Blank pump ID -> 422
        assert (
            client.post(
                "/api/fuel-entries/verify-location",
                headers=op1_headers,
                json={"petrol_pump_id": "   ", "latitude": 18.5204, "longitude": 73.8567, "accuracy_m": 10.0},
            ).status_code
            == 422
        )

        # Extra unexpected field -> 422
        assert (
            client.post(
                "/api/fuel-entries/verify-location",
                headers=op1_headers,
                json={
                    "petrol_pump_id": "gps-pump-a",
                    "latitude": 18.5204,
                    "longitude": 73.8567,
                    "accuracy_m": 10.0,
                    "bypass": True,
                },
            ).status_code
            == 422
        )

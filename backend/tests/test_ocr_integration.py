"""
Tesseract OCR Integration Tests
-------------------------------
Tests end-to-end Tesseract OCR verification during fuel entry submission:
1. Matching odometer & fuel quantity photos -> MATCH, needs_manual_review=False.
2. Mismatched odometer photo -> MISMATCH, needs_manual_review=True, ocr_notes populated.
3. Mismatched fuel receipt photo -> MISMATCH, needs_manual_review=True.
4. Unreadable/blank photo -> UNREADABLE, needs_manual_review=True.
5. Ambiguous multi-number photo -> UNREADABLE, needs_manual_review=True.
6. Owner review still works cleanly on OCR-flagged entries.
"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models import PetrolPump, User, Vehicle


def make_ocr_image_bytes(text: str | None = None) -> bytes:
    image = Image.new("RGB", (600, 200), "white")
    if text:
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("Arial.ttf", 80)
        except OSError:
            font = ImageFont.load_default()
        draw.text((50, 50), text, fill="black", font=font)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def ocr_client(tmp_path, monkeypatch):
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
        owner = User(id="ocr-owner", username="ocr_owner", password_hash="h", role="owner", is_active=True)
        operator = User(id="ocr-op", username="ocr_op", password_hash="h", role="operator", is_active=True)
        vehicle = Vehicle(id="ocr-veh", vehicle_number="MH-12-OCR-1", initial_odometer=44000.0, is_active=True)
        pump = PetrolPump(
            id="ocr-pump",
            name="OCR Test Pump",
            latitude=18.5204,
            longitude=73.8567,
            radius_meters=150.0,
            is_active=True,
        )
        db.add_all([owner, operator, vehicle, pump])
        db.commit()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    op_headers = {"Authorization": f"Bearer {create_access_token('ocr-op', 'operator')}"}
    owner_headers = {"Authorization": f"Bearer {create_access_token('ocr-owner', 'owner')}"}

    try:
        with TestClient(app) as client:
            yield client, op_headers, owner_headers
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _submit_with_images(client, op_headers, odo_value, fuel_value, odo_text, receipt_text):
    gps_res = client.post(
        "/api/fuel-entries/verify-location",
        headers=op_headers,
        json={"petrol_pump_id": "ocr-pump", "latitude": 18.5204, "longitude": 73.8567, "accuracy_m": 10.0},
    )
    assert gps_res.status_code == 200
    gps_token = gps_res.json()["gps_verification_token"]

    uploads = []
    for ptype, text in (("PLATE", "MH12"), ("ODOMETER", odo_text), ("RECEIPT", receipt_text)):
        up_res = client.post(
            "/api/fuel-entries/upload-photo",
            headers=op_headers,
            data={"photo_type": ptype, "petrol_pump_id": "ocr-pump", "gps_verification_token": gps_token},
            files={"file": (f"{ptype.lower()}.png", io.BytesIO(make_ocr_image_bytes(text)), "image/png")},
        )
        assert up_res.status_code == 200, up_res.text
        uploads.append({"photo_type": ptype, "photo_url": up_res.json()["photo_url"]})

    return client.post(
        "/api/fuel-entries/",
        headers=op_headers,
        json={
            "vehicle_id": "ocr-veh",
            "petrol_pump_id": "ocr-pump",
            "gps_verification_token": gps_token,
            "current_odometer": odo_value,
            "fuel_litres": fuel_value,
            "is_full_tank": True,
            "latitude": 18.5204,
            "longitude": 73.8567,
            "accuracy_m": 10.0,
            "photos": uploads,
        },
    )


def test_ocr_exact_match_passes_without_review_flag(ocr_client):
    client, op_headers, owner_headers = ocr_client
    res = _submit_with_images(
        client,
        op_headers,
        odo_value=45600.0,
        fuel_value=25.50,
        odo_text="45600",
        receipt_text="25.50",
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["ocr_odometer_status"] == "MATCH"
    assert data["ocr_odometer_value"] == 45600.0
    assert data["ocr_fuel_status"] == "MATCH"
    assert data["ocr_fuel_value"] == 25.5
    assert data["needs_manual_review"] is False
    assert data["ocr_notes"] is None

    # Owner detail view reflects OCR verification fields
    detail = client.get(f"/api/fuel-entries/{data['id']}", headers=owner_headers)
    assert detail.status_code == 200
    assert detail.json()["needs_manual_review"] is False


def test_ocr_mismatch_flags_entry_for_owner_review(ocr_client):
    client, op_headers, owner_headers = ocr_client
    res = _submit_with_images(
        client,
        op_headers,
        odo_value=45600.0,
        fuel_value=50.0,
        odo_text="45100",
        receipt_text="30.00",
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["ocr_odometer_status"] == "MISMATCH"
    assert data["ocr_odometer_value"] == 45100.0
    assert data["ocr_fuel_status"] == "MISMATCH"
    assert data["ocr_fuel_value"] == 30.0
    assert data["needs_manual_review"] is True
    assert "Odometer mismatch" in data["ocr_notes"]
    assert "Fuel quantity mismatch" in data["ocr_notes"]

    # Owner can reject the flagged entry
    reject_res = client.patch(
        f"/api/fuel-entries/{data['id']}/verify",
        headers=owner_headers,
        json={"status": "REJECTED", "rejection_reason": "OCR detected lower odometer and fuel"},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "REJECTED"


def test_ocr_unreadable_and_ambiguous_images_flagged(ocr_client):
    client, op_headers, _ = ocr_client
    res = _submit_with_images(
        client,
        op_headers,
        odo_value=45600.0,
        fuel_value=50.0,
        odo_text=None,
        receipt_text="50.00  4500.00",
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["ocr_odometer_status"] == "UNREADABLE"
    assert data["ocr_odometer_value"] is None
    assert data["ocr_fuel_status"] == "UNREADABLE"
    assert data["ocr_fuel_value"] is None
    assert data["needs_manual_review"] is True
    assert data["ocr_notes"] is not None

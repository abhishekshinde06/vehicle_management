"""
Integration Tests for Fuel Entry Access Control
and Dashboard Filters.
"""

import io
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.models import User, Vehicle, PetrolPump, FuelEntry


@pytest.fixture
def isolated_client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "USE_S3", False)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

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


def make_token(user_id: str, role: str) -> str:
    return create_access_token(
        subject=user_id,
        role=role,
    )


def get_gps_token(client, headers, pump_id):
    response = client.post(
        "/api/fuel-entries/verify-location",
        headers=headers,
        json={
            "petrol_pump_id": pump_id,
            "latitude": 18.5,
            "longitude": 73.8,
            "accuracy_m": 10.0,
        },
    )

    assert response.status_code == 200, response.text

    return response.json()["gps_verification_token"]


def upload_three_photos(
    client,
    headers,
    pump_id,
    gps_token,
):
    photos = []

    for photo_type in ("PLATE", "ODOMETER", "RECEIPT"):
        buffer = io.BytesIO()

        Image.new("RGB", (100, 100), "white").save(
            buffer,
            format="JPEG",
        )

        buffer.seek(0)

        response = client.post(
            "/api/fuel-entries/upload-photo",
            headers=headers,
            data={
                "photo_type": photo_type,
                "petrol_pump_id": pump_id,
                "gps_verification_token": gps_token,
            },
            files={
                "file": (
                    "test.jpg",
                    buffer,
                    "image/jpeg",
                )
            },
        )

        assert response.status_code == 200, response.text

        photos.append({
            "photo_type": photo_type,
            "photo_url": response.json()["photo_url"],
        })

    return photos


def test_operator_access_restrictions(isolated_client):
    client, TestingSession = isolated_client

    with TestingSession() as db:
        owner = User(
            username="fleet_owner",
            password_hash="h",
            role="owner",
            is_active=True,
        )

        op1 = User(
            username="operator_one",
            password_hash="h",
            role="operator",
            is_active=True,
        )

        op2 = User(
            username="operator_two",
            password_hash="h",
            role="operator",
            is_active=True,
        )

        v1 = Vehicle(
            vehicle_number="MH-12-TEST-1",
            initial_odometer=1000.0,
            is_active=True,
        )

        v2 = Vehicle(
            vehicle_number="MH-12-TEST-2",
            initial_odometer=2000.0,
            is_active=True,
        )

        p1 = PetrolPump(
            name="Pump 1",
            latitude=18.5,
            longitude=73.8,
            radius_meters=100.0,
            is_active=True,
        )

        db.add_all([owner, op1, op2, v1, v2, p1])
        db.commit()

        owner_id = owner.id
        op1_id = op1.id
        op2_id = op2.id

        v1_id = v1.id
        v2_id = v2.id
        p1_id = p1.id

        # Seed baseline fuel entries.
        base1 = FuelEntry(
            vehicle_id=v1_id,
            petrol_pump_id=p1_id,
            operator_id=op1_id,
            current_odometer=1000.0,
            previous_odometer=1000.0,
            fuel_litres=50.0,
            is_full_tank=True,
            status="APPROVED",
        )

        base2 = FuelEntry(
            vehicle_id=v2_id,
            petrol_pump_id=p1_id,
            operator_id=op2_id,
            current_odometer=2000.0,
            previous_odometer=2000.0,
            fuel_litres=50.0,
            is_full_tank=True,
            status="APPROVED",
        )

        db.add_all([base1, base2])
        db.commit()

    op1_headers = {
        "Authorization": f"Bearer {make_token(op1_id, 'operator')}"
    }

    op2_headers = {
        "Authorization": f"Bearer {make_token(op2_id, 'operator')}"
    }

    owner_headers = {
        "Authorization": f"Bearer {make_token(owner_id, 'owner')}"
    }

    # Generate separate GPS tokens for both operators.
    op1_gps_token = get_gps_token(
        client, op1_headers, p1_id
    )

    op2_gps_token = get_gps_token(
        client, op2_headers, p1_id
    )

    # Operator 1 submits an entry.
    res1 = client.post(
        "/api/fuel-entries/",
        headers=op1_headers,
        json={
            "vehicle_id": v1_id,
            "petrol_pump_id": p1_id,
            "gps_verification_token": op1_gps_token,
            "current_odometer": 1500.0,
            "fuel_litres": 50.0,
            "is_full_tank": True,
            "latitude": 18.5001,
            "longitude": 73.8001,
            "accuracy_m": 10.0,
            "photos": upload_three_photos(
                client,
                op1_headers,
                p1_id,
                op1_gps_token,
            ),
        },
    )

    assert res1.status_code == 201, res1.text

    entry1_id = res1.json()["id"]

    # Operator 2 submits an entry.
    res2 = client.post(
        "/api/fuel-entries/",
        headers=op2_headers,
        json={
            "vehicle_id": v2_id,
            "petrol_pump_id": p1_id,
            "gps_verification_token": op2_gps_token,
            "current_odometer": 2500.0,
            "fuel_litres": 60.0,
            "is_full_tank": True,
            "latitude": 18.5001,
            "longitude": 73.8001,
            "accuracy_m": 10.0,
            "photos": upload_three_photos(
                client,
                op2_headers,
                p1_id,
                op2_gps_token,
            ),
        },
    )

    assert res2.status_code == 201, res2.text

    entry2_id = res2.json()["id"]

    # Operator 1 can see only their own entries.
    op1_list = client.get(
        "/api/fuel-entries/",
        headers=op1_headers,
    ).json()

    assert all(
        e["operator_id"] == op1_id for e in op1_list
    )

    assert any(
        e["id"] == entry1_id for e in op1_list
    )

    assert not any(
        e["id"] == entry2_id for e in op1_list
    )

    # Operator 2 can see only their own entries.
    op2_list = client.get(
        "/api/fuel-entries/",
        headers=op2_headers,
    ).json()

    assert all(
        e["operator_id"] == op2_id for e in op2_list
    )

    assert any(
        e["id"] == entry2_id for e in op2_list
    )

    assert not any(
        e["id"] == entry1_id for e in op2_list
    )

    # Owner can see entries from both operators.
    owner_list = client.get(
        "/api/fuel-entries/",
        headers=owner_headers,
    ).json()

    owner_ids = [e["id"] for e in owner_list]

    assert entry1_id in owner_ids
    assert entry2_id in owner_ids

    # Operator 1 can view their own entry.
    response = client.get(
        f"/api/fuel-entries/{entry1_id}",
        headers=op1_headers,
    )

    assert response.status_code == 200

    # Operator 2 cannot view Operator 1's entry.
    forbidden_res = client.get(
        f"/api/fuel-entries/{entry1_id}",
        headers=op2_headers,
    )

    assert forbidden_res.status_code == 403

    assert (
        "Operators can only view their own fuel entries"
        in forbidden_res.json()["detail"]
    )

    # Owner can view any entry.
    response = client.get(
        f"/api/fuel-entries/{entry1_id}",
        headers=owner_headers,
    )

    assert response.status_code == 200

    # Operator cannot approve entries.
    verify_by_op = client.patch(
        f"/api/fuel-entries/{entry1_id}/verify",
        headers=op1_headers,
        json={"status": "APPROVED"},
    )

    assert verify_by_op.status_code == 403


def test_dashboard_filters(isolated_client):
    client, TestingSession = isolated_client

    with TestingSession() as db:
        owner = User(
            username="filter_owner",
            password_hash="h",
            role="owner",
            is_active=True,
        )

        op = User(
            username="filter_operator",
            password_hash="h",
            role="operator",
            is_active=True,
        )

        v1 = Vehicle(
            vehicle_number="MH-14-FLT-1",
            initial_odometer=1000.0,
            is_active=True,
        )

        v2 = Vehicle(
            vehicle_number="MH-14-FLT-2",
            initial_odometer=2000.0,
            is_active=True,
        )

        p1 = PetrolPump(
            name="Pump A",
            latitude=18.5,
            longitude=73.8,
            radius_meters=100.0,
            is_active=True,
        )

        p2 = PetrolPump(
            name="Pump B",
            latitude=18.6,
            longitude=73.9,
            radius_meters=100.0,
            is_active=True,
        )

        db.add_all([owner, op, v1, v2, p1, p2])
        db.commit()

        t0 = datetime(2026, 11, 10, 10, 0, 0)
        t1 = datetime(2026, 11, 15, 12, 0, 0)
        t2 = datetime(2026, 11, 20, 14, 0, 0)

        e1 = FuelEntry(
            vehicle_id=v1.id,
            petrol_pump_id=p1.id,
            operator_id=op.id,
            current_odometer=1200.0,
            previous_odometer=1000.0,
            fuel_litres=25.0,
            is_full_tank=True,
            status="APPROVED",
            created_at=t0,
        )

        e2 = FuelEntry(
            vehicle_id=v1.id,
            petrol_pump_id=p2.id,
            operator_id=op.id,
            current_odometer=1400.0,
            previous_odometer=1200.0,
            fuel_litres=30.0,
            is_full_tank=False,
            status="PENDING",
            created_at=t1,
        )

        e3 = FuelEntry(
            vehicle_id=v2.id,
            petrol_pump_id=p1.id,
            operator_id=op.id,
            current_odometer=2300.0,
            previous_odometer=2000.0,
            fuel_litres=40.0,
            is_full_tank=True,
            status="REJECTED",
            rejection_reason="Bad photo",
            created_at=t2,
        )

        db.add_all([e1, e2, e3])
        db.commit()

        owner_token = make_token(owner.id, "owner")

        v1_id, v2_id = v1.id, v2.id
        p1_id, p2_id = p1.id, p2.id
        e1_id, e2_id, e3_id = e1.id, e2.id, e3.id

    headers = {
        "Authorization": f"Bearer {owner_token}"
    }

    # Filter by vehicle.
    res_v1 = client.get(
        f"/api/fuel-entries/?vehicle_id={v1_id}",
        headers=headers,
    ).json()

    assert len(res_v1) == 2

    assert all(
        e["vehicle_id"] == v1_id for e in res_v1
    )

    # Filter by petrol pump.
    res_p2 = client.get(
        f"/api/fuel-entries/?petrol_pump_id={p2_id}",
        headers=headers,
    ).json()

    assert len(res_p2) == 1
    assert res_p2[0]["id"] == e2_id

    # Filter by status.
    res_status = client.get(
        "/api/fuel-entries/?status=REJECTED",
        headers=headers,
    ).json()

    assert len(res_status) == 1
    assert res_status[0]["id"] == e3_id

    # Filter by start date.
    res_start = client.get(
        "/api/fuel-entries/?start_date=2026-11-15T00:00:00",
        headers=headers,
    ).json()

    ids = [e["id"] for e in res_start]

    assert e1_id not in ids
    assert e2_id in ids
    assert e3_id in ids

    # Filter by date range.
    res_range = client.get(
        "/api/fuel-entries/"
        "?start_date=2026-11-12T00:00:00"
        "&end_date=2026-11-18T23:59:59",
        headers=headers,
    ).json()

    assert len(res_range) == 1
    assert res_range[0]["id"] == e2_id

    # Invalid date range must be rejected.
    invalid_range_res = client.get(
        "/api/fuel-entries/"
        "?start_date=2026-11-25"
        "&end_date=2026-11-10",
        headers=headers,
    )

    assert invalid_range_res.status_code == 400

    assert (
        "Invalid date range"
        in invalid_range_res.json()["detail"]
    )


def test_schema_validations_over_http(isolated_client):
    client, TestingSession = isolated_client

    with TestingSession() as db:
        op = User(
            username="http_val_op",
            password_hash="h",
            role="operator",
            is_active=True,
        )

        v = Vehicle(
            vehicle_number="MH-12-HTTP-1",
            initial_odometer=1000.0,
            is_active=True,
        )

        p = PetrolPump(
            name="HTTP Pump",
            latitude=18.5,
            longitude=73.8,
            radius_meters=100.0,
            is_active=True,
        )

        db.add_all([op, v, p])
        db.commit()

        op_id = op.id
        v_id = v.id
        p_id = p.id

    headers = {
        "Authorization": f"Bearer {make_token(op_id, 'operator')}"
    }

    gps_token = get_gps_token(
        client, headers, p_id
    )

    base_payload = {
        "vehicle_id": v_id,
        "petrol_pump_id": p_id,
        "gps_verification_token": gps_token,
        "current_odometer": 1200.0,
        "fuel_litres": 30.0,
        "is_full_tank": True,
        "latitude": 18.5,
        "longitude": 73.8,
        "accuracy_m": 10.0,
        "photos": upload_three_photos(
            client,
            headers,
            p_id,
            gps_token,
        ),
    }

    # Duplicate photo URLs -> 422.
    dup_payload = dict(base_payload)

    dup_payload["photos"] = [
        {
            "photo_type": "PLATE",
            "photo_url": "/uploads/same.jpg",
        },
        {
            "photo_type": "ODOMETER",
            "photo_url": "/uploads/same.jpg",
        },
        {
            "photo_type": "RECEIPT",
            "photo_url": "/uploads/r.jpg",
        },
    ]

    response = client.post(
        "/api/fuel-entries/",
        json=dup_payload,
        headers=headers,
    )

    assert response.status_code == 422

    # Blank photo URL -> 422.
    blank_payload = dict(base_payload)

    blank_payload["photos"] = [
        {
            "photo_type": "PLATE",
            "photo_url": "   ",
        },
        {
            "photo_type": "ODOMETER",
            "photo_url": "/uploads/o.jpg",
        },
        {
            "photo_type": "RECEIPT",
            "photo_url": "/uploads/r.jpg",
        },
    ]

    response = client.post(
        "/api/fuel-entries/",
        json=blank_payload,
        headers=headers,
    )

    assert response.status_code == 422

    # Unexpected request field -> 422.
    extra_payload = dict(base_payload)

    extra_payload["unauthorized_bonus_field"] = "hack"

    response = client.post(
        "/api/fuel-entries/",
        json=extra_payload,
        headers=headers,
    )

    assert response.status_code == 422

    # Legacy direct photo field -> 422.
    legacy_payload = dict(base_payload)

    legacy_payload["photo_plate_url"] = "/uploads/legacy.jpg"

    response = client.post(
        "/api/fuel-entries/",
        json=legacy_payload,
        headers=headers,
    )

    assert response.status_code == 422

    # NaN and infinite numeric values -> 422.
    for bad_val in ["NaN", "Infinity", "-Infinity"]:
        for field in [
            "current_odometer",
            "fuel_litres",
            "accuracy_m",
            "latitude",
            "longitude",
        ]:
            bad_payload = dict(base_payload)
            bad_payload[field] = bad_val

            response = client.post(
                "/api/fuel-entries/",
                json=bad_payload,
                headers=headers,
            )

            assert response.status_code == 422, (
                f"Failed to reject {bad_val} for {field}"
            )
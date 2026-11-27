"""
Concurrent Submission & Alembic Migration Tests
-----------------------------------------------
Validates:
1. Concurrent fuel entry submissions for the same vehicle serialize safely.
2. Concurrent owner verification (approve/reject) allows only one winner (200 + 409).
3. Alembic migrations 0001 -> 0005 upgrade and downgrade cleanly on SQLite,
   and generate valid PostgreSQL DDL offline (plus optional live PostgreSQL test
   when POSTGRES_TEST_DATABASE_URL is configured).
"""

import io
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token
from app.main import app
from app.models import AuditLog, FuelEntry, PetrolPump, User, Vehicle


def make_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def concurrent_env(tmp_path, monkeypatch):
    db_path = tmp_path / "concurrent_test.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "USE_S3", False)
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(upload_dir))

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        owner = User(id="conc-owner", username="conc_owner", password_hash="h", role="owner", is_active=True)
        operator = User(id="conc-op", username="conc_op", password_hash="h", role="operator", is_active=True)
        vehicle = Vehicle(id="conc-veh", vehicle_number="MH-12-CONC-1", initial_odometer=10000.0, is_active=True)
        pump = PetrolPump(
            id="conc-pump",
            name="Concurrent Pump",
            latitude=18.5204,
            longitude=73.8567,
            radius_meters=150.0,
            is_active=True,
        )
        db.add_all([owner, operator, vehicle, pump])
        db.commit()

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    op_headers = {"Authorization": f"Bearer {create_access_token('conc-op', 'operator')}"}
    owner_headers = {"Authorization": f"Bearer {create_access_token('conc-owner', 'owner')}"}

    try:
        with TestClient(app) as client:
            yield client, TestingSession, op_headers, owner_headers
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _upload_photo_set(client, op_headers):
    gps_res = client.post(
        "/api/fuel-entries/verify-location",
        headers=op_headers,
        json={"petrol_pump_id": "conc-pump", "latitude": 18.5204, "longitude": 73.8567, "accuracy_m": 10.0},
    )
    assert gps_res.status_code == 200
    gps_token = gps_res.json()["gps_verification_token"]

    photos = []
    for ptype in ("PLATE", "ODOMETER", "RECEIPT"):
        res = client.post(
            "/api/fuel-entries/upload-photo",
            headers=op_headers,
            data={"photo_type": ptype, "petrol_pump_id": "conc-pump", "gps_verification_token": gps_token},
            files={"file": (f"{ptype.lower()}.jpg", io.BytesIO(make_jpeg_bytes()), "image/jpeg")},
        )
        assert res.status_code == 200
        photos.append({"photo_type": ptype, "photo_url": res.json()["photo_url"]})

    return gps_token, photos


def test_concurrent_same_odometer_submissions_for_vehicle(concurrent_env):
    client, TestingSession, op_headers, _ = concurrent_env
    gps_token_1, photos_1 = _upload_photo_set(client, op_headers)
    gps_token_2, photos_2 = _upload_photo_set(client, op_headers)

    barrier = Barrier(2)

    def submit(token, photos):
        barrier.wait()
        return client.post(
            "/api/fuel-entries/",
            headers=op_headers,
            json={
                "vehicle_id": "conc-veh",
                "petrol_pump_id": "conc-pump",
                "gps_verification_token": token,
                "current_odometer": 10500.0,
                "fuel_litres": 50.0,
                "is_full_tank": True,
                "latitude": 18.5204,
                "longitude": 73.8567,
                "accuracy_m": 10.0,
                "photos": photos,
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(submit, gps_token_1, photos_1)
        f2 = pool.submit(submit, gps_token_2, photos_2)
        r1, r2 = f1.result(), f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [201, 400], f"Expected [201, 400], got {[r1.status_code, r2.status_code]}"

    with TestingSession() as db:
        assert db.query(FuelEntry).count() == 1


def test_concurrent_owner_verification_only_succeeds_once(concurrent_env):
    client, TestingSession, op_headers, owner_headers = concurrent_env
    gps_token, photos = _upload_photo_set(client, op_headers)

    create_res = client.post(
        "/api/fuel-entries/",
        headers=op_headers,
        json={
            "vehicle_id": "conc-veh",
            "petrol_pump_id": "conc-pump",
            "gps_verification_token": gps_token,
            "current_odometer": 10500.0,
            "fuel_litres": 50.0,
            "is_full_tank": True,
            "latitude": 18.5204,
            "longitude": 73.8567,
            "accuracy_m": 10.0,
            "photos": photos,
        },
    )
    assert create_res.status_code == 201
    entry_id = create_res.json()["id"]

    barrier = Barrier(2)

    def review(payload):
        barrier.wait()
        return client.patch(
            f"/api/fuel-entries/{entry_id}/verify",
            headers=owner_headers,
            json=payload,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(review, {"status": "APPROVED"})
        f2 = pool.submit(review, {"status": "REJECTED", "rejection_reason": "Concurrent reject"})
        r1, r2 = f1.result(), f2.result()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [200, 409], f"Expected [200, 409], got {[r1.status_code, r2.status_code]}"

    with TestingSession() as db:
        logs = db.query(AuditLog).filter(AuditLog.fuel_entry_id == entry_id).all()
        assert len(logs) == 2  # CREATED + exactly one review action


class TestAlembicMigrations:
    def _make_alembic_config(self, db_url: str) -> Config:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg = Config(os.path.join(backend_dir, "alembic.ini"))
        cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        cfg.set_main_option("sqlalchemy.url", db_url)
        return cfg

    def test_alembic_upgrade_downgrade_sqlite(self, tmp_path, monkeypatch):
        db_file = tmp_path / "alembic_check.db"
        db_url = f"sqlite:///{db_file}"
        monkeypatch.setattr(settings, "DATABASE_URL", db_url)

        cfg = self._make_alembic_config(db_url)
        command.upgrade(cfg, "head")

        engine = create_engine(db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"users", "vehicles", "petrol_pumps", "fuel_entries", "entry_photos", "uploaded_photos", "audit_logs"} <= tables

        fuel_cols = {col["name"] for col in inspector.get_columns("fuel_entries")}
        assert {
            "ocr_odometer_status",
            "ocr_odometer_value",
            "ocr_fuel_status",
            "ocr_fuel_value",
            "needs_manual_review",
            "ocr_notes",
        } <= fuel_cols

        uploaded_cols = {col["name"] for col in inspector.get_columns("uploaded_photos")}
        assert {"id", "uploader_id", "petrol_pump_id", "photo_type", "storage_reference", "is_used"} <= uploaded_cols
        engine.dispose()

        command.downgrade(cfg, "base")
        engine = create_engine(db_url)
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
        engine.dispose()

        command.upgrade(cfg, "head")

    def test_alembic_postgresql_offline_sql_generation(self, monkeypatch, capsys):
        pg_url = "postgresql+psycopg2://postgres:password@localhost:5432/vehicle_management"
        monkeypatch.setattr(settings, "DATABASE_URL", pg_url)

        cfg = self._make_alembic_config(pg_url)
        command.upgrade(cfg, "head", sql=True)

        captured = capsys.readouterr().out
        assert "CREATE TABLE uploaded_photos" in captured
        assert "uq_petrol_pumps_name_ci" in captured
        assert "needs_manual_review" in captured
        assert "petrol_pump_id" in captured

    def test_live_postgresql_migrations_when_configured(self, monkeypatch):
        pg_url = os.getenv("POSTGRES_TEST_DATABASE_URL")
        if not pg_url:
            pytest.skip("POSTGRES_TEST_DATABASE_URL not set; skipping live PostgreSQL migration test")

        monkeypatch.setattr(settings, "DATABASE_URL", pg_url)
        cfg = self._make_alembic_config(pg_url)
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        engine = create_engine(pg_url)
        assert "uploaded_photos" in inspect(engine).get_table_names()
        engine.dispose()

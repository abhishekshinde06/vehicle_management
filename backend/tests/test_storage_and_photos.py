"""
Photo Upload, Validation, Storage & Access Control Tests
--------------------------------------------------------
Isolated tests validating:
1. Pillow image validation (empty, corrupted, unsupported format, >5 MB rejected; JPEG/PNG/WEBP accepted).
2. Local storage default vs S3 storage enabled (no silent fallback to local on S3 failure).
3. Removal of public `/uploads` static mount (returns 404).
4. Authenticated photo retrieval (`GET /api/fuel-entries/photos/{photo_id}`):
   - Unauthenticated -> 401
   - Owner -> 200 for all entries
   - Operator -> 200 for own uploads/entries, 403 for other operators' photos
5. Fuel entry submission validation:
   - Non-existent photo -> 404
   - Unrecognized/arbitrary URL -> 400
   - Photo belonging to another operator -> 403
   - Photo type mismatch -> 400
   - Already-used photo -> 409
6. Concurrent reuse protection (parallel submissions referencing the same photo).
"""

import io
import os
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app
from app.models import EntryPhoto, FuelEntry, PetrolPump, UploadedPhoto, User, Vehicle
from app.services.storage import (
    ImageTooLargeError,
    ImageValidationError,
    StorageError,
    read_image,
    save_image,
    validate_image_bytes,
)


def make_image_bytes(fmt: str = "JPEG", size=(32, 32), color=(20, 120, 220)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format=fmt)
    return buf.getvalue()
def get_gps_token(client, headers):
    response = client.post(
        "/api/fuel-entries/verify-location",
        json={
            "petrol_pump_id": "pump-photo-1",
            "latitude": 18.5204,
            "longitude": 73.8567,
            "accuracy_m": 10.0,
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text

    return response.json()["gps_verification_token"]


def make_upload_data(client, headers, photo_type):
    return {
        "photo_type": photo_type,
        "petrol_pump_id": "pump-photo-1",
        "gps_verification_token": get_gps_token(client, headers),
    }

@pytest.fixture
def isolated_env():
    """Creates an isolated temp SQLite database and temp UPLOAD_DIR per test."""
    temp_dir = tempfile.TemporaryDirectory()
    db_path = os.path.join(temp_dir.name, "test_photos.db")
    upload_dir = os.path.join(temp_dir.name, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    engine = create_engine(
    f"sqlite:///{db_path}",
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSession() as db:
        op1 = User(
            id="op-photo-1",
            username="photo_op_1",
            password_hash=get_password_hash("operator123"),
            role="operator",
            full_name="Operator One",
            is_active=True,
        )
        op2 = User(
            id="op-photo-2",
            username="photo_op_2",
            password_hash=get_password_hash("operator123"),
            role="operator",
            full_name="Operator Two",
            is_active=True,
        )
        owner = User(
            id="owner-photo-1",
            username="photo_owner_1",
            password_hash=get_password_hash("owner123"),
            role="owner",
            full_name="Fleet Owner",
            is_active=True,
        )
        vehicle = Vehicle(
            id="v-photo-1",
            vehicle_number="MH-12-PH-9999",
            model="Tata Signa",
            initial_odometer=10000.0,
            is_active=True,
        )
        pump = PetrolPump(
            id="pump-photo-1",
            name="Expressway HP Hub",
            latitude=18.5204,
            longitude=73.8567,
            radius_meters=150.0,
            is_active=True,
        )
        db.add_all([op1, op2, owner, vehicle, pump])
        db.commit()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    op1_headers = {"Authorization": f"Bearer {create_access_token(subject='op-photo-1', role='operator')}"}
    op2_headers = {"Authorization": f"Bearer {create_access_token(subject='op-photo-2', role='operator')}"}
    owner_headers = {"Authorization": f"Bearer {create_access_token(subject='owner-photo-1', role='owner')}"}

    with patch.object(settings, "UPLOAD_DIR", upload_dir), \
         patch.object(settings, "USE_S3", False):
        with TestClient(app) as client:
            yield {
                "client": client,
                "Session": TestingSession,
                "upload_dir": upload_dir,
                "op1_headers": op1_headers,
                "op2_headers": op2_headers,
                "owner_headers": owner_headers,
            }

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    temp_dir.cleanup()


class TestImageValidationUnit:
    def test_valid_jpeg_png_webp(self):
        for fmt, expected_ext, expected_mime in [
            ("JPEG", ".jpg", "image/jpeg"),
            ("PNG", ".png", "image/png"),
            ("WEBP", ".webp", "image/webp"),
        ]:
            ext, mime = validate_image_bytes(make_image_bytes(fmt))
            assert ext == expected_ext
            assert mime == expected_mime

    def test_rejects_empty_bytes(self):
        with pytest.raises(ImageValidationError, match="empty"):
            validate_image_bytes(b"")

    def test_rejects_corrupted_or_spoofed_bytes(self):
        with pytest.raises(ImageValidationError):
            validate_image_bytes(b"\xff\xd8\xff\xe0not-a-real-jpeg")

    def test_rejects_unsupported_image_format_gif(self):
        gif_bytes = make_image_bytes("GIF")
        with pytest.raises(ImageValidationError, match="Unsupported image format"):
            validate_image_bytes(gif_bytes)

    def test_rejects_oversized_image_over_5mb(self):
        too_big = b"x" * (5 * 1024 * 1024 + 1)
        with pytest.raises(ImageTooLargeError, match="5 MB"):
            validate_image_bytes(too_big)


class TestStorageBackendBehavior:
    def test_local_storage_default(self, isolated_env):
        img = make_image_bytes("JPEG")
        res = save_image(img, "local_test.jpg", "image/jpeg")
        assert res["storage_type"] == "local"
        assert res["storage_reference"] == "local_test.jpg"
        assert os.path.isfile(os.path.join(isolated_env["upload_dir"], "local_test.jpg"))
        assert read_image("local_test.jpg", "local") == img

    def test_s3_enabled_failure_does_not_fallback_to_local(self, isolated_env):
        mock_s3 = MagicMock()
        mock_s3.put_object.side_effect = RuntimeError("S3 unavailable")

        with patch.object(settings, "USE_S3", True), \
             patch.object(settings, "AWS_ACCESS_KEY_ID", "test-key"), \
             patch.object(settings, "AWS_SECRET_ACCESS_KEY", "test-secret"), \
             patch.object(settings, "S3_BUCKET_NAME", "test-bucket"), \
             patch("app.services.storage.get_s3_client", return_value=mock_s3):
            with pytest.raises(StorageError, match="Failed to store photo in S3"):
                save_image(make_image_bytes("JPEG"), "no_fallback.jpg", "image/jpeg")

        # Confirm nothing was written to local disk
        assert not os.path.exists(os.path.join(isolated_env["upload_dir"], "no_fallback.jpg"))

    def test_s3_enabled_missing_credentials_raises_storage_error(self, isolated_env):
        with patch.object(settings, "USE_S3", True), \
             patch.object(settings, "AWS_ACCESS_KEY_ID", ""), \
             patch.object(settings, "AWS_SECRET_ACCESS_KEY", ""):
            with pytest.raises(StorageError, match="missing required settings"):
                save_image(make_image_bytes("JPEG"), "missing_creds.jpg", "image/jpeg")

    def test_s3_upload_and_read_success(self, isolated_env):
        img = make_image_bytes("PNG")
        mock_body = MagicMock()
        mock_body.read.return_value = img
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {"Body": mock_body}

        with patch.object(settings, "USE_S3", True), \
             patch.object(settings, "AWS_ACCESS_KEY_ID", "test-key"), \
             patch.object(settings, "AWS_SECRET_ACCESS_KEY", "test-secret"), \
             patch.object(settings, "S3_BUCKET_NAME", "test-bucket"), \
             patch("app.services.storage.get_s3_client", return_value=mock_s3):
            saved = save_image(img, "s3_plate.png", "image/png")
            assert saved["storage_type"] == "s3"
            assert saved["storage_reference"] == "uploads/s3_plate.png"
            fetched = read_image(saved["storage_reference"], "s3")
            assert fetched == img
            mock_s3.put_object.assert_called_once()
            mock_s3.get_object.assert_called_once()


class TestPhotoUploadAndRetrievalAPI:
    def test_public_uploads_mount_is_disabled(self, isolated_env):
        client = isolated_env["client"]
        res = client.post(
            "/api/fuel-entries/upload-photo",
            data=make_upload_data(
            client, isolated_env["op1_headers"], "PLATE"
            ),
            files={"file": ("plate.jpg", io.BytesIO(make_image_bytes("JPEG")), "image/jpeg")},
            headers=isolated_env["op1_headers"],
        )
        assert res.status_code == 200
        # Public /uploads/<filename> must return 404
        photo_id = res.json()["photo_id"]
        assert client.get(f"/uploads/{photo_id}.jpg").status_code == 404

    def test_upload_validations_over_http(self, isolated_env):
        client = isolated_env["client"]
        headers = isolated_env["op1_headers"]

        # Unauthenticated -> 401
        assert (
            client.post(
                "/api/fuel-entries/upload-photo",
                data=make_upload_data(client, headers, "PLATE"),
                files={"file": ("plate.jpg", io.BytesIO(make_image_bytes("JPEG")), "image/jpeg")},
            ).status_code
            == 401
        )

        # Invalid photo_type -> 400
        assert (
            client.post(
                "/api/fuel-entries/upload-photo",
                data=make_upload_data(client, headers, "SELFIE"),
                files={"file": ("plate.jpg", io.BytesIO(make_image_bytes("JPEG")), "image/jpeg")},
                headers=headers,
            ).status_code
            == 400
        )

        # Empty file -> 400
        assert (
            client.post(
                "/api/fuel-entries/upload-photo",
                data=make_upload_data(client, headers, "PLATE"),
                files={"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")},
                headers=headers,
            ).status_code
            == 400
        )

        # Spoofed/corrupted file -> 400
        assert (
            client.post(
                "/api/fuel-entries/upload-photo",
                data=make_upload_data(client, headers, "PLATE"),
                files={"file": ("fake.jpg", io.BytesIO(b"not really an image"), "image/jpeg")},
                headers=headers,
            ).status_code
            == 400
        )

        # Oversized > 5 MB -> 413
                # Oversized > 5 MB -> 413
        oversized = io.BytesIO(
            b"\xff\xd8\xff\xe0" + b"0" * (5 * 1024 * 1024)
        )

        assert (
            client.post(
                "/api/fuel-entries/upload-photo",
                data=make_upload_data(client, headers, "PLATE"),
                files={"file": ("big.jpg", oversized, "image/jpeg")},
                headers=headers,
            ).status_code
            == 413
        )

    def test_authenticated_photo_retrieval_rbac(self, isolated_env):
        client = isolated_env["client"]
        img_bytes = make_image_bytes("PNG")

        up_res = client.post(
            "/api/fuel-entries/upload-photo",
            data=make_upload_data(
                client, isolated_env["op1_headers"], "PLATE"
            ),
            files={"file": ("plate.png", io.BytesIO(img_bytes), "image/png")},
            headers=isolated_env["op1_headers"],
        )
        assert up_res.status_code == 200
        photo_url = up_res.json()["photo_url"]

        # Unauthenticated -> 401
        assert client.get(photo_url).status_code == 401

        # Other operator -> 403
        assert client.get(photo_url, headers=isolated_env["op2_headers"]).status_code == 403

        # Uploader operator -> 200
        op1_res = client.get(photo_url, headers=isolated_env["op1_headers"])
        assert op1_res.status_code == 200
        assert op1_res.content == img_bytes
        assert op1_res.headers["content-type"].startswith("image/png")

        # Owner -> 200
        owner_res = client.get(photo_url, headers=isolated_env["owner_headers"])
        assert owner_res.status_code == 200
        assert owner_res.content == img_bytes


class TestFuelEntryPhotoValidationAndConcurrency:
    def _upload_three(self, client, headers):
        uploaded = {}
        for ptype in ("PLATE", "ODOMETER", "RECEIPT"):
            res = client.post(
                "/api/fuel-entries/upload-photo",
                data=make_upload_data(client, headers, ptype),
                files={"file": (f"{ptype.lower()}.jpg", io.BytesIO(make_image_bytes("JPEG")), "image/jpeg")},
                headers=headers,
            )
            assert res.status_code == 200, res.text
            uploaded[ptype] = res.json()
        return uploaded

    def test_submission_validates_existence_ownership_type_and_reuse(self, isolated_env):
        client = isolated_env["client"]
        op1_headers = isolated_env["op1_headers"]
        op2_headers = isolated_env["op2_headers"]

        op1_photos = self._upload_three(client, op1_headers)
        op2_photos = self._upload_three(client, op2_headers)

        base_payload = {
            "vehicle_id": "v-photo-1",
            "petrol_pump_id": "pump-photo-1",
            "gps_verification_token": get_gps_token(client, op1_headers),
            "current_odometer": 10500.0,
            "fuel_litres": 50.0,
            "is_full_tank": True,
            "latitude": 18.5204,
            "longitude": 73.8567,
            "accuracy_m": 10.0,
        }

        # 1. Arbitrary/legacy /uploads path rejected -> 400
        res_arbitrary = client.post(
            "/api/fuel-entries/",
            json={
                **base_payload,
                "photos": [
                    {"photo_type": "PLATE", "photo_url": "/uploads/fake1.jpg"},
                    {"photo_type": "ODOMETER", "photo_url": "/uploads/fake2.jpg"},
                    {"photo_type": "RECEIPT", "photo_url": "/uploads/fake3.jpg"},
                ],
            },
            headers=op1_headers,
        )
        assert res_arbitrary.status_code == 400

        # 2. Non-existent photo ID -> 404
        res_missing = client.post(
            "/api/fuel-entries/",
            json={
                **base_payload,
                "photos": [
                    {"photo_type": "PLATE", "photo_url": f"/api/fuel-entries/photos/{uuid.uuid4()}"},
                    {"photo_type": "ODOMETER", "photo_url": op1_photos["ODOMETER"]["photo_url"]},
                    {"photo_type": "RECEIPT", "photo_url": op1_photos["RECEIPT"]["photo_url"]},
                ],
            },
            headers=op1_headers,
        )
        assert res_missing.status_code == 404

        # 3. Photo belonging to another operator -> 403
        res_foreign = client.post(
            "/api/fuel-entries/",
            json={
                **base_payload,
                "photos": [
                    {"photo_type": "PLATE", "photo_url": op2_photos["PLATE"]["photo_url"]},
                    {"photo_type": "ODOMETER", "photo_url": op1_photos["ODOMETER"]["photo_url"]},
                    {"photo_type": "RECEIPT", "photo_url": op1_photos["RECEIPT"]["photo_url"]},
                ],
            },
            headers=op1_headers,
        )
        assert res_foreign.status_code == 403

        # 4. Photo type mismatch -> 400
        res_mismatch = client.post(
            "/api/fuel-entries/",
            json={
                **base_payload,
                "photos": [
                    {"photo_type": "PLATE", "photo_url": op1_photos["ODOMETER"]["photo_url"]},
                    {"photo_type": "ODOMETER", "photo_url": op1_photos["PLATE"]["photo_url"]},
                    {"photo_type": "RECEIPT", "photo_url": op1_photos["RECEIPT"]["photo_url"]},
                ],
            },
            headers=op1_headers,
        )
        assert res_mismatch.status_code == 400

        # 5. Valid submission -> 201
        valid_payload = {
            **base_payload,
            "photos": [
                {"photo_type": "PLATE", "photo_url": op1_photos["PLATE"]["photo_url"]},
                {"photo_type": "ODOMETER", "photo_url": op1_photos["ODOMETER"]["photo_url"]},
                {"photo_type": "RECEIPT", "photo_url": op1_photos["RECEIPT"]["photo_url"]},
            ],
        }
        res_ok = client.post("/api/fuel-entries/", json=valid_payload, headers=op1_headers)
        assert res_ok.status_code == 201, res_ok.text
        entry_data = res_ok.json()
        assert entry_data["photo_plate_url"] == op1_photos["PLATE"]["photo_url"]

        # Confirm DB tracks is_used=True
        with isolated_env["Session"]() as db:
            for ptype in ("PLATE", "ODOMETER", "RECEIPT"):
                row = db.query(UploadedPhoto).filter(UploadedPhoto.id == op1_photos[ptype]["photo_id"]).first()
                assert row.is_used is True
                assert row.fuel_entry_id == entry_data["id"]

        # 6. Reuse of already-used photo -> 409
        res_reuse = client.post(
            "/api/fuel-entries/",
            json={**valid_payload, "current_odometer": 10600.0},
            headers=op1_headers,
        )
        assert res_reuse.status_code == 409

        # 7. Owner can access entry photos via authenticated URL, other operator gets 403
        assert client.get(entry_data["photo_plate_url"], headers=isolated_env["owner_headers"]).status_code == 200
        assert client.get(entry_data["photo_plate_url"], headers=op2_headers).status_code == 403

    def test_concurrent_photo_reuse_prevented(self, isolated_env):
        client = isolated_env["client"]
        op1_headers = isolated_env["op1_headers"]
        op1_photos = self._upload_three(client, op1_headers)
        gps_token = get_gps_token(client, op1_headers)
        def submit_with_odo(odo: float):
            return client.post(
                "/api/fuel-entries/",
                json={
                    "vehicle_id": "v-photo-1",
                    "petrol_pump_id": "pump-photo-1",
                    "gps_verification_token": gps_token,
                    "current_odometer": odo,
                    "fuel_litres": 40.0,
                    "is_full_tank": True,
                    "latitude": 18.5204,
                    "longitude": 73.8567,
                    "accuracy_m": 10.0,
                    "photos": [
                        {"photo_type": "PLATE", "photo_url": op1_photos["PLATE"]["photo_url"]},
                        {"photo_type": "ODOMETER", "photo_url": op1_photos["ODOMETER"]["photo_url"]},
                        {"photo_type": "RECEIPT", "photo_url": op1_photos["RECEIPT"]["photo_url"]},
                    ],
                },
                headers=op1_headers,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(submit_with_odo, 10500.0)
            f2 = pool.submit(submit_with_odo, 10550.0)
            r1, r2 = f1.result(), f2.result()

        statuses = sorted([r1.status_code, r2.status_code])
        assert statuses == [201, 409], f"Expected [201, 409], got {[r1.status_code, r2.status_code]}"

        with isolated_env["Session"]() as db:
            assert db.query(FuelEntry).count() == 1
            assert db.query(EntryPhoto).count() == 3

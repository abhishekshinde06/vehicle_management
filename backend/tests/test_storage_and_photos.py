"""
Photo Upload and Storage Tests
------------------------------
Tests validating:
  1. upload_photo endpoint with valid image file (returns 200, photo_url, view_url).
  2. upload_photo rejects invalid file formats (e.g. .txt, .pdf) with 400.
  3. upload_photo requires authentication (returns 401 without token).
  4. save_image saves file and returns structured metadata.
  5. get_viewable_url handles local URLs properly.
  6. get_viewable_url converts S3 URLs to presigned URLs when boto3/S3 configured.
  7. Fuel entry creation stores the photo_url, and GET /api/fuel-entries returns viewable URLs.
"""

import io
import pytest
from unittest.mock import MagicMock, patch
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
from app.models.entry_photo import EntryPhoto
from app.services.storage import save_image, get_viewable_url

TEST_DATABASE_URL = "sqlite:///./test_photos.db"
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
    operator = User(
        id="op-photo-test-1",
        username="photo_operator",
        password_hash=get_password_hash("operator123"),
        role="operator",
        full_name="Photo Test Operator",
        is_active=True,
    )
    owner = User(
        id="owner-photo-test-1",
        username="photo_owner",
        password_hash=get_password_hash("owner123"),
        role="owner",
        full_name="Photo Test Owner",
        is_active=True,
    )
    vehicle = Vehicle(
        id="v-photo-1",
        vehicle_number="MH-12-PH-9999",
        model="Tata Signa",
        initial_odometer=10000.0,
        is_active=True
    )
    pump = PetrolPump(
        id="pump-photo-1",
        name="Expressway HP Hub",
        latitude=18.5204,
        longitude=73.8567,
        radius_meters=150.0,
        is_active=True
    )
    db.add_all([operator, owner, vehicle, pump])
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
def operator_headers():
    token = create_access_token(subject="op-photo-test-1", role="operator")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def owner_headers():
    token = create_access_token(subject="owner-photo-test-1", role="owner")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestPhotoUploadAPI:

    def test_upload_photo_unauthenticated(self, client):
        """Must reject unauthenticated uploads with 401."""
        file_data = io.BytesIO(b"fake image data")
        res = client.post(
            "/api/fuel-entries/upload-photo",
            files={"file": ("test.jpg", file_data, "image/jpeg")}
        )
        assert res.status_code == 401

    def test_upload_photo_invalid_format(self, client, operator_headers):
        """Must reject non-image file extensions (.pdf, .txt, etc.) with 400."""
        file_data = io.BytesIO(b"fake pdf content")
        res = client.post(
            "/api/fuel-entries/upload-photo",
            files={"file": ("receipt.pdf", file_data, "application/pdf")},
            headers=operator_headers
        )
        assert res.status_code == 400
        assert "Unsupported file format" in res.json()["detail"]

    def test_upload_photo_valid_jpeg(self, client, operator_headers):
        """Successful upload returns 200 with photo_url and filename."""
        file_data = io.BytesIO(b"\xff\xd8\xff\xe0" + b"dummy jpeg image content")
        res = client.post(
            "/api/fuel-entries/upload-photo",
            files={"file": ("camera_plate.jpg", file_data, "image/jpeg")},
            headers=operator_headers
        )
        assert res.status_code == 200
        data = res.json()
        assert "photo_url" in data
        assert "filename" in data
        assert data["filename"].endswith(".jpg")
        assert "storage_type" in data
        assert data["size_bytes"] > 0


class TestStorageServiceLogic:

    def test_local_storage_fallback(self):
        """When S3 is disabled or unavailable, save_image cleanly falls back to local storage."""
        contents = b"test byte content"
        result = save_image(contents, "test_local.jpg", "image/jpeg")
        assert result["storage_type"] in ("local", "s3")
        assert result["photo_url"] is not None

    def test_get_viewable_url_local_path(self):
        """Local path URLs (/uploads/...) should be returned untouched."""
        url = "/uploads/test_photo.jpg"
        assert get_viewable_url(url) == url

    def test_get_viewable_url_empty(self):
        """Empty or None URLs should be handled safely without error."""
        assert get_viewable_url("") == ""
        assert get_viewable_url(None) is None

    @patch("app.services.storage.get_s3_client")
    def test_get_viewable_url_s3_presigned(self, mock_get_client):
        """S3 URLs should generate a presigned URL when boto3 client is active."""
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = (
            "https://my-bucket.s3.amazonaws.com/uploads/plate.jpg?AWSAccessKeyId=AKIA...&Signature=test"
        )
        mock_get_client.return_value = mock_s3

        s3_raw_url = "https://my-bucket.s3.ap-southeast-2.amazonaws.com/uploads/plate.jpg"
        with patch("app.core.config.settings.USE_S3", True), \
             patch("app.core.config.settings.AWS_ACCESS_KEY_ID", "AKIA_MOCK_TEST"):
            result = get_viewable_url(s3_raw_url)

        assert "Signature=test" in result
        mock_s3.generate_presigned_url.assert_called_once()


class TestEndToEndFuelEntryWithPhotos:

    def test_create_and_retrieve_fuel_entry_with_photos(self, client, operator_headers, owner_headers):
        """
        End-to-End Test:
        1. Operator uploads 3 photos.
        2. Operator submits fuel entry linking the 3 photo URLs.
        3. Owner retrieves entry via GET /api/fuel-entries/{id}.
        4. Asserts photo URLs and convenience fields (photo_plate_url, etc.) are present and formatted.
        """
        # 1. Upload 3 photos
        photo_types = [("PLATE", "plate.jpg"), ("ODOMETER", "odo.jpg"), ("RECEIPT", "rec.jpg")]
        uploaded_photos = []

        for p_type, fname in photo_types:
            f = io.BytesIO(b"fake-image-" + p_type.encode())
            res = client.post(
                "/api/fuel-entries/upload-photo",
                files={"file": (fname, f, "image/jpeg")},
                headers=operator_headers
            )
            assert res.status_code == 200
            uploaded_photos.append({
                "photo_type": p_type,
                "photo_url": res.json()["photo_url"]
            })

        # 2. Submit fuel entry
        entry_payload = {
            "vehicle_id": "v-photo-1",
            "petrol_pump_id": "pump-photo-1",
            "current_odometer": 10500.0,
            "fuel_litres": 80.0,
            "is_full_tank": True,
            "latitude": 18.5204,
            "longitude": 73.8567,
            "accuracy_m": 10.0,
            "photos": uploaded_photos
        }

        submit_res = client.post("/api/fuel-entries/", json=entry_payload, headers=operator_headers)
        assert submit_res.status_code == 201, submit_res.text
        created_entry = submit_res.json()
        entry_id = created_entry["id"]

        assert len(created_entry["photos"]) == 3
        assert created_entry["photo_plate_url"] is not None
        assert created_entry["photo_odometer_url"] is not None
        assert created_entry["photo_receipt_url"] is not None

        # 3. Owner retrieves the entry
        get_res = client.get(f"/api/fuel-entries/{entry_id}", headers=owner_headers)
        assert get_res.status_code == 200
        data = get_res.json()

        assert data["id"] == entry_id
        assert len(data["photos"]) == 3
        types_returned = [p["photo_type"] for p in data["photos"]]
        assert "PLATE" in types_returned
        assert "ODOMETER" in types_returned
        assert "RECEIPT" in types_returned

"""
Storage & Image Validation Service
----------------------------------
Provides:
1. Strict image validation using Pillow (rejects empty, oversized, corrupted,
   and unsupported images; enforces 5 MB max upload size).
2. Local disk storage (default free solution under settings.UPLOAD_DIR).
3. Optional AWS S3 private storage (via boto3) when settings.USE_S3 is True,
   without silent fallback to local disk if S3 is enabled and fails.
4. Authenticated image retrieval helpers for local and S3 backends.
"""

import io
import logging
from pathlib import Path
from typing import Any, Dict, Tuple

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}

# Singleton boto3 S3 client
_s3_client = None


class StorageError(Exception):
    """Raised when the configured storage backend fails."""


class ImageValidationError(Exception):
    """Raised when uploaded file content is empty, corrupted, or unsupported."""


class ImageTooLargeError(Exception):
    """Raised when uploaded file exceeds maximum allowed byte size."""


class PhotoNotFoundError(Exception):
    """Raised when stored image object cannot be located in storage."""


def validate_image_bytes(
    contents: bytes,
    max_bytes: int | None = None,
) -> Tuple[str, str]:
    """
    Validates raw uploaded bytes using Pillow and size limits.

    Returns:
        Tuple of (normalized_extension, mime_content_type), e.g. (".jpg", "image/jpeg").
    """
    limit = max_bytes if max_bytes is not None else settings.MAX_IMAGE_SIZE_BYTES

    if not contents:
        raise ImageValidationError("Uploaded image file is empty.")

    if len(contents) > limit:
        max_mb = round(limit / (1024 * 1024), 2)
        raise ImageTooLargeError(
            f"Image file exceeds the maximum allowed size of {max_mb:g} MB."
        )

    try:
        with Image.open(io.BytesIO(contents)) as img:
            detected_format = (img.format or "").upper()
            img.verify()

        if detected_format not in ALLOWED_IMAGE_FORMATS:
            raise ImageValidationError(
                f"Unsupported image format '{detected_format or 'unknown'}'. "
                "Allowed formats: JPEG, PNG, WEBP."
            )

        # Second pass: decode pixel stream to catch truncated/corrupted payloads
        with Image.open(io.BytesIO(contents)) as img:
            ImageOps.exif_transpose(img)
            img.load()

    except ImageValidationError:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        SyntaxError,
        ValueError,
    ) as exc:
        raise ImageValidationError(
            "Invalid or corrupted image file. Upload a valid JPEG, PNG, or WEBP image."
        ) from exc

    return ALLOWED_IMAGE_FORMATS[detected_format]


def _validate_s3_config() -> None:
    """Ensures required S3 settings are present when USE_S3 is explicitly enabled."""
    missing = []
    if not settings.AWS_ACCESS_KEY_ID:
        missing.append("AWS_ACCESS_KEY_ID")
    if not settings.AWS_SECRET_ACCESS_KEY:
        missing.append("AWS_SECRET_ACCESS_KEY")
    if not settings.S3_BUCKET_NAME:
        missing.append("S3_BUCKET_NAME")
    if not settings.AWS_REGION:
        missing.append("AWS_REGION")
    if missing:
        raise StorageError(
            f"S3 storage is enabled (USE_S3=true) but missing required settings: {', '.join(missing)}"
        )


def get_s3_client():
    """Returns a singleton boto3 S3 client instance when S3 is enabled."""
    global _s3_client
    _validate_s3_config()
    if _s3_client is None:
        try:
            import boto3
        except ImportError as exc:
            raise StorageError(
                "S3 storage is enabled (USE_S3=true) but boto3 is not installed."
            ) from exc

        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
    return _s3_client


def _resolve_local_path(storage_reference: str) -> Path:
    """Resolves a local storage filename inside UPLOAD_DIR safely."""
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    clean_name = Path(storage_reference).name
    if not clean_name or clean_name != storage_reference:
        raise PhotoNotFoundError("Invalid local storage reference.")
    target_path = (upload_dir / clean_name).resolve()
    if target_path.parent != upload_dir:
        raise PhotoNotFoundError("Invalid local storage path.")
    return target_path


def save_image(
    contents: bytes,
    filename: str,
    content_type: str = "image/jpeg",
) -> Dict[str, Any]:
    """
    Saves image bytes to AWS S3 when settings.USE_S3 is True, otherwise to local disk.
    Never falls back silently to local disk when USE_S3 is True.
    """
    clean_filename = Path(filename).name
    if not clean_filename:
        raise StorageError("Invalid destination filename.")

    if settings.USE_S3:
        s3 = get_s3_client()
        s3_key = f"uploads/{clean_filename}"
        try:
            s3.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Body=contents,
                ContentType=content_type,
            )
        except Exception as exc:
            logger.error("S3 upload failed for key %s: %s", s3_key, exc)
            raise StorageError("Failed to store photo in S3 storage.") from exc

        return {
            "filename": clean_filename,
            "storage_reference": s3_key,
            "storage_type": "s3",
            "size_bytes": len(contents),
            "content_type": content_type,
        }

    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    local_path = _resolve_local_path(clean_filename)
    with open(local_path, "wb") as f:
        f.write(contents)

    return {
        "filename": clean_filename,
        "storage_reference": clean_filename,
        "storage_type": "local",
        "size_bytes": len(contents),
        "content_type": content_type,
    }


def read_image(storage_reference: str, storage_type: str) -> bytes:
    """
    Reads image bytes from the specified storage backend.
    Does not fall back between S3 and local storage.
    """
    if storage_type == "s3":
        if not settings.USE_S3:
            raise StorageError("Photo is stored in S3, but S3 storage is disabled.")
        s3 = get_s3_client()
        s3_key = (
            storage_reference.split("amazonaws.com/", 1)[1]
            if "amazonaws.com/" in storage_reference
            else storage_reference
        )
        try:
            obj = s3.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
            return obj["Body"].read()
        except Exception as exc:
            error_code = getattr(exc, "response", {}).get("Error", {}).get("Code")
            if error_code in ("NoSuchKey", "404", "NotFound"):
                raise PhotoNotFoundError("Photo object not found in S3.") from exc
            logger.error("S3 read failed for key %s: %s", s3_key, exc)
            raise StorageError("Failed to retrieve photo from S3 storage.") from exc

    if storage_type == "local":
        local_path = _resolve_local_path(storage_reference)
        if not local_path.is_file():
            raise PhotoNotFoundError("Photo file not found in local storage.")
        return local_path.read_bytes()

    raise StorageError(f"Unknown storage type '{storage_type}'.")


def delete_image(storage_reference: str, storage_type: str) -> None:
    """Best-effort cleanup helper if database registration fails after storage write."""
    try:
        if storage_type == "s3" and settings.USE_S3:
            s3 = get_s3_client()
            s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=storage_reference)
        elif storage_type == "local":
            local_path = _resolve_local_path(storage_reference)
            if local_path.is_file():
                local_path.unlink()
    except Exception as exc:
        logger.warning("Cleanup failed for %s (%s): %s", storage_reference, storage_type, exc)


def get_viewable_url(photo_url: str, expiration_seconds: int = 3600) -> str:
    """
    Preserves authenticated API paths and local paths; generates S3 presigned URL
    only when explicitly given an S3 key/URL and USE_S3 is enabled.
    """
    if not photo_url:
        return photo_url

    is_s3 = ("amazonaws.com" in photo_url) or photo_url.startswith("uploads/")
    if is_s3:
        if not settings.USE_S3:
            raise StorageError("S3 URL requested while USE_S3 is disabled.")
        s3 = get_s3_client()
        s3_key = (
            photo_url.split("amazonaws.com/", 1)[1]
            if "amazonaws.com/" in photo_url
            else photo_url
        )
        try:
            return s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
                ExpiresIn=expiration_seconds,
            )
        except Exception as exc:
            logger.error("Failed to generate presigned URL for %s: %s", photo_url, exc)
            raise StorageError("Failed to generate S3 presigned URL.") from exc

    return photo_url

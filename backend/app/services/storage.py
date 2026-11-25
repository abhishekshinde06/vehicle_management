"""
Storage Service
---------------
Provides file storage abstraction supporting both:
1. AWS S3 private storage (via boto3) when settings.USE_S3 is True.
   - Files are stored privately in S3.
   - Temporary viewable presigned URLs are generated on demand.
2. Local disk storage (under settings.UPLOAD_DIR) as fallback when USE_S3 is False or boto3 is unavailable.
"""

import os
import uuid
import logging
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

# Singleton boto3 S3 client
_s3_client = None


def get_s3_client():
    """Returns a singleton boto3 S3 client instance, or None if boto3 is not installed."""
    global _s3_client
    if _s3_client is None:
        try:
            import boto3
        except ImportError:
            logger.warning("boto3 is not installed. S3 uploads disabled.")
            return None

        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
    return _s3_client


def save_image(contents: bytes, filename: str, content_type: str = "image/jpeg") -> Dict[str, Any]:
    """
    Saves image bytes privately to AWS S3 if enabled, otherwise saves to local UPLOAD_DIR.

    Args:
        contents: Raw bytes of the image file.
        filename: Destination filename (e.g. 'plate_abc123.jpg').
        content_type: MIME type (e.g. 'image/jpeg', 'image/png').

    Returns:
        Dict with keys:
            filename: Name/Key of the saved file.
            photo_url: Stored reference path (or S3 key).
            storage_type: 's3' or 'local'.
            size_bytes: Size of the image in bytes.
    """
    if settings.USE_S3 and settings.AWS_ACCESS_KEY_ID and settings.S3_BUCKET_NAME:
        try:
            s3 = get_s3_client()
            if s3 is not None:
                s3_key = f"uploads/{filename}"

                # Store file privately in S3 (default is private, no public ACL)
                s3.put_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=s3_key,
                    Body=contents,
                    ContentType=content_type,
                )

                # Generate a temporary presigned URL so the operator can immediately see what they uploaded
                presigned_url = s3.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={
                        "Bucket": settings.S3_BUCKET_NAME,
                        "Key": s3_key,
                    },
                    ExpiresIn=3600,  # 1 hour validity
                )

                # Store the canonical S3 path in DB, return presigned URL for display
                canonical_s3_url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"

                return {
                    "filename": filename,
                    "photo_url": canonical_s3_url,
                    "view_url": presigned_url,
                    "storage_type": "s3",
                    "size_bytes": len(contents),
                    "content_type": content_type
                }
        except Exception as exc:
            logger.error(f"S3 upload failed: {exc}. Falling back to local disk storage.")

    # Fallback: Local disk storage
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    local_path = os.path.join(settings.UPLOAD_DIR, filename)
    with open(local_path, "wb") as f:
        f.write(contents)

    local_url = f"/uploads/{filename}"
    return {
        "filename": filename,
        "photo_url": local_url,
        "view_url": local_url,
        "storage_type": "local",
        "size_bytes": len(contents),
        "content_type": content_type
    }


def get_viewable_url(photo_url: str, expiration_seconds: int = 3600) -> str:
    """
    Converts a stored photo_url into a temporary viewable URL.
    - If photo_url is stored in a private S3 bucket, generates a signed presigned URL with expiration.
    - If photo_url is local (e.g. /uploads/...), returns it as-is.
    """
    if not photo_url:
        return photo_url

    # Check if photo_url is an S3 reference
    is_s3 = ("amazonaws.com" in photo_url) or photo_url.startswith("uploads/")

    if is_s3 and settings.USE_S3 and settings.AWS_ACCESS_KEY_ID:
        try:
            s3 = get_s3_client()
            if s3 is not None:
                # Extract S3 key (e.g., 'uploads/filename.jpg')
                if "amazonaws.com/" in photo_url:
                    s3_key = photo_url.split("amazonaws.com/")[1]
                else:
                    s3_key = photo_url

                return s3.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={
                        "Bucket": settings.S3_BUCKET_NAME,
                        "Key": s3_key,
                    },
                    ExpiresIn=expiration_seconds,
                )
        except Exception as exc:
            logger.error(f"Failed to generate presigned URL for {photo_url}: {exc}")

    return photo_url

"""
Uploaded Photo Model
--------------------
Tracks every uploaded camera photo prior to and after attachment to a FuelEntry:
- `uploader_id`: User who uploaded the photo.
- `photo_type`: Intended category ('PLATE', 'ODOMETER', 'RECEIPT').
- `storage_type`: Storage backend ('local' or 's3').
- `storage_reference`: Local filename or S3 object key.
- `is_used`: Whether the photo has already been consumed by a FuelEntry.
- `fuel_entry_id`: Linked FuelEntry ID once consumed.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class UploadedPhoto(Base):
    __tablename__ = "uploaded_photos"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    uploader_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    petrol_pump_id = Column(
    String,
    ForeignKey("petrol_pumps.id"),
    nullable=True,
    index=True,
    )
    photo_type = Column(String, nullable=False)  # "PLATE", "ODOMETER", "RECEIPT"
    storage_type = Column(String, nullable=False, default="local")  # "local" or "s3"
    storage_reference = Column(String, nullable=False, unique=True)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    is_used = Column(Boolean, nullable=False, default=False, index=True)
    fuel_entry_id = Column(
        String,
        ForeignKey("fuel_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    used_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    uploader = relationship("User")
    fuel_entry = relationship("FuelEntry")
    petrol_pump = relationship("PetrolPump")
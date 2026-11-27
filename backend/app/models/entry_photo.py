"""
Entry Photo Model
-----------------
Stores photo attachments associated with a fueling entry:
- 'PLATE': Live photo of the vehicle license plate.
- 'ODOMETER': Live photo of the vehicle dashboard odometer meter.
- 'RECEIPT': Live photo of the fuel pump display or printed fuel receipt.

Links uniquely to `uploaded_photos.id` so a single uploaded photo cannot be
attached concurrently or repeatedly to multiple fuel entries.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class EntryPhoto(Base):
    __tablename__ = "entry_photos"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    fuel_entry_id = Column(
        String,
        ForeignKey("fuel_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_photo_id = Column(
        String,
        ForeignKey("uploaded_photos.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    photo_type = Column(String, nullable=False)  # "PLATE", "ODOMETER", "RECEIPT"
    photo_url = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    fuel_entry = relationship("FuelEntry", back_populates="photos")
    uploaded_photo = relationship("UploadedPhoto")

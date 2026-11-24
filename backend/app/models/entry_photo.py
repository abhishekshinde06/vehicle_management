"""
Entry Photo Model
-----------------
Stores photo attachments associated with a fueling entry:
- 'PLATE': Live photo of the vehicle license plate.
- 'ODOMETER': Live photo of the vehicle dashboard odometer meter.
- 'RECEIPT': Live photo of the fuel pump display or printed fuel receipt.

Separating photos into a distinct table gives us:
1. Dynamic photo handling (allows adding extra photos without modifying table schema).
2. Storage of photo-specific metadata (upload timestamp, file format, s3 key).
3. Clean separation of concerns between tabular transactional data and media assets.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class EntryPhoto(Base):
    __tablename__ = "entry_photos"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    fuel_entry_id = Column(String, ForeignKey("fuel_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    photo_type = Column(String, nullable=False)  # "PLATE", "ODOMETER", "RECEIPT"
    photo_url = Column(String, nullable=False)   # Relative path or Cloud S3 URL
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Back-reference to the parent FuelEntry
    fuel_entry = relationship("FuelEntry", back_populates="photos")

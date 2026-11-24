import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime
from app.core.database import Base

class PetrolPump(Base):
    __tablename__ = "petrol_pumps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True, nullable=False)  # e.g., "HP Highway Fuel Stop, Pune"
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)  # GPS latitude
    longitude = Column(Float, nullable=False)  # GPS longitude
    radius_meters = Column(Float, default=100.0, nullable=False)  # Allowed geofence radius
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime
from app.core.database import Base

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_number = Column(String, unique=True, index=True, nullable=False)  # e.g., "MH-12-AB-1234"
    model = Column(String, nullable=True)  # e.g., "Tata Prima 4028.S"
    initial_odometer = Column(Float, default=0.0, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

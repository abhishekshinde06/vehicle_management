"""
Fuel Entry Model
----------------
Represents the core fueling transaction for a vehicle at an authorized petrol pump.
Includes odometer readings, fuel filled, computed distance, and mileage.
Media photos are linked via the 1-to-many relationship with `EntryPhoto`.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class FuelEntry(Base):
    __tablename__ = "fuel_entries"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=False, index=True)

    petrol_pump_id = Column(String, ForeignKey("petrol_pumps.id"), nullable=False, index=True)
    
    operator_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Readings and Fuel Volume
    current_odometer = Column(Float, nullable=False)
    previous_odometer = Column(Float, nullable=False, default=0.0)
    fuel_litres = Column(Float, nullable=False)
    is_full_tank = Column(Boolean, default=True, nullable=False)

    # Calculated Performance Metrics
    distance_km = Column(Float, nullable=True)   # current_odometer - previous_odometer
    mileage_kmpl = Column(Float, nullable=True)  # distance_km / fuel_litres

    # GPS Location & Geofence Metadata
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    accuracy_m = Column(Float, nullable=True)
    distance_from_pump_m = Column(Float, nullable=True)
    is_location_verified = Column(Boolean, default=True)

    # Verification Workflow
    status = Column(String, default="PENDING", index=True)  # "PENDING", "APPROVED", "REJECTED"
    rejection_reason = Column(String, nullable=True)
    reviewed_by = Column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    vehicle = relationship("Vehicle")
    petrol_pump = relationship("PetrolPump")
    operator = relationship("User", foreign_keys=[operator_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])

    # 1-to-Many relationship with EntryPhoto (Cascades deletion if an entry is removed)
    photos = relationship("EntryPhoto", back_populates="fuel_entry", cascade="all, delete-orphan", lazy="joined")

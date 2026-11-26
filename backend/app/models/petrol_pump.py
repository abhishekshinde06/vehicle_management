import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Float, Boolean, DateTime,
    UniqueConstraint, Index, func
)

from app.core.database import Base


class PetrolPump(Base):
    __tablename__ = "petrol_pumps"

    id = Column(
        String, primary_key=True,
        default=lambda: str(uuid.uuid4())
    )

    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_meters = Column(Float, default=100.0, nullable=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index(
            "uq_petrol_pumps_name_ci",
            func.lower(func.trim(name)),
            unique=True
        ),
        UniqueConstraint(
            "latitude",
            "longitude",
            name="uq_petrol_pumps_lat_lon"
        ),
    )
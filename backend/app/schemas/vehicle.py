from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class VehicleBase(BaseModel):
    vehicle_number: str
    model: Optional[str] = None
    initial_odometer: float = 0.0

class VehicleCreate(VehicleBase):
    pass

class VehicleResponse(VehicleBase):
    id: str
    is_active: bool
    latest_odometer: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

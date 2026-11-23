from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class PetrolPumpBase(BaseModel):
    name: str
    address: Optional[str] = None
    latitude: float
    longitude: float
    radius_meters: float = 100.0

class PetrolPumpCreate(PetrolPumpBase):
    pass

class PetrolPumpResponse(PetrolPumpBase):
    id: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

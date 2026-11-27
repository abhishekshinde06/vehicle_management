from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class VehicleBase(BaseModel):
    vehicle_number: str = Field(..., min_length=1, max_length=50)
    model: Optional[str] = Field(default=None, max_length=100)
    initial_odometer: float = Field(default=0.0, ge=0, allow_inf_nan=False)


class VehicleCreate(VehicleBase):
    model_config = ConfigDict(extra="forbid")

    @field_validator("vehicle_number")
    @classmethod
    def validate_vehicle_number(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Vehicle number cannot be empty or blank")
        return stripped

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class VehicleResponse(VehicleBase):
    id: str
    is_active: bool
    latest_odometer: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

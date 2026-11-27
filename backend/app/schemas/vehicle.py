import re
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

VEHICLE_NUMBER_REGEX = re.compile(
    r"^([A-Z]{2}[-\s]?\d{1,2}[-\s]?[A-Z]{1,3}[-\s]?\d{1,4}|\d{2}[-\s]?BH[-\s]?\d{4}[-\s]?[A-Z]{1,2})$"
)


class VehicleBase(BaseModel):
    vehicle_number: str = Field(..., min_length=1, max_length=50)
    model: Optional[str] = Field(default=None, max_length=100)
    initial_odometer: float = Field(default=0.0, ge=0, allow_inf_nan=False)


class VehicleCreate(VehicleBase):
    model_config = ConfigDict(extra="forbid")

    @field_validator("vehicle_number")
    @classmethod
    def validate_vehicle_number(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("Vehicle number cannot be empty or blank")
        if not VEHICLE_NUMBER_REGEX.match(normalized):
            raise ValueError(
                "Invalid vehicle number format. Expected format like MH-12-AB-1234 or MH12AB1234."
            )
        return normalized

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

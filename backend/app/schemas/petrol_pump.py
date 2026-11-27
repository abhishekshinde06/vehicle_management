from typing import Optional
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PetrolPumpBase(BaseModel):
    name: str
    address: Optional[str] = None

    latitude: float = Field(
        ge=-90, le=90, allow_inf_nan=False
    )

    longitude: float = Field(
        ge=-180, le=180, allow_inf_nan=False
    )

    radius_meters: float = Field(
        default=100.0, gt=0, allow_inf_nan=False
    )


class PetrolPumpCreate(PetrolPumpBase):

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Petrol pump name cannot be empty.")

        return value


class PetrolPumpResponse(PetrolPumpBase):
    id: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
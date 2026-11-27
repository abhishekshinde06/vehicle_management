from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeofenceVerifyRequest(BaseModel):
    petrol_pump_id: str = Field(..., min_length=1)

    latitude: float = Field(..., ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(..., ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float = Field(..., ge=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")

    @field_validator("petrol_pump_id")
    @classmethod
    def validate_pump_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("petrol_pump_id cannot be empty or blank")
        return stripped

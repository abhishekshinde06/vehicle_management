from pydantic import BaseModel, Field


class GeofenceVerifyRequest(BaseModel):
    petrol_pump_id: str

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_m: float = Field(..., ge=0, allow_inf_nan=False)
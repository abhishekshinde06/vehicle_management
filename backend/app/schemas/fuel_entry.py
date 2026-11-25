import math
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator


# Schema for an individual attached photo
class EntryPhotoBase(BaseModel):
    photo_type: str = Field(..., pattern="^(PLATE|ODOMETER|RECEIPT)$", description="Type of photo: PLATE, ODOMETER, or RECEIPT")
    photo_url: str = Field(..., min_length=1, description="Storage URL or relative path to the image")

    model_config = ConfigDict(extra="forbid")

    @field_validator("photo_url")
    @classmethod
    def validate_photo_url_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Photo URL cannot be empty or blank")
        return v.strip()


class EntryPhotoCreate(EntryPhotoBase):
    pass


class EntryPhotoResponse(EntryPhotoBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="ignore")


# Schema for creating a new fuel entry
class FuelEntryCreate(BaseModel):
    vehicle_id: str
    petrol_pump_id: str
    current_odometer: float = Field(..., gt=0, allow_inf_nan=False, description="Current odometer reading")
    fuel_litres: float = Field(..., gt=0, allow_inf_nan=False, description="Fuel filled in litres")
    is_full_tank: bool = Field(default=True, description="True if filled to full tank")

    # List of attached photos (stored in entry_photos table)
    photos: List[EntryPhotoCreate] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly three photos: PLATE, ODOMETER, RECEIPT"
    )

    # GPS coordinates for geofencing check
    latitude: float = Field(..., ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(..., ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float = Field(..., ge=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")

    @field_validator("current_odometer", "fuel_litres", "accuracy_m", "latitude", "longitude", mode="before")
    @classmethod
    def validate_finite_numbers(cls, v):
        if isinstance(v, (int, float)) and not math.isfinite(v):
            raise ValueError("Numeric value must be finite (not NaN or Inf)")
        return v

    @model_validator(mode="after")
    def validate_required_photos(self):
        """
        Ensure all three required photo types are provided exactly once,
        with non-empty and non-duplicate URLs.
        """
        required_types = {"PLATE", "ODOMETER", "RECEIPT"}

        if not self.photos or len(self.photos) != 3:
            raise ValueError(
                "Exactly one PLATE, ODOMETER and RECEIPT photo is required"
            )

        photo_types = [photo.photo_type for photo in self.photos]

        if set(photo_types) != required_types or len(photo_types) != 3:
            raise ValueError(
                "Exactly one PLATE, ODOMETER and RECEIPT photo is required"
            )

        urls = []
        for photo in self.photos:
            stripped_url = photo.photo_url.strip() if photo.photo_url else ""
            if not stripped_url:
                raise ValueError("Photo URL cannot be empty")
            urls.append(stripped_url)

        if len(set(urls)) != len(urls):
            raise ValueError("Duplicate photo URLs are not allowed")

        return self
# Schema for Owner verification action
class FuelEntryVerify(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    rejection_reason: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


# Schema for Fuel Entry response
class FuelEntryResponse(BaseModel):
    id: str
    vehicle_id: str
    petrol_pump_id: str
    operator_id: str

    current_odometer: float
    previous_odometer: float
    fuel_litres: float
    is_full_tank: bool

    distance_km: Optional[float] = None
    mileage_kmpl: Optional[float] = None

    # Relational list of photos from the entry_photos table
    photos: List[EntryPhotoResponse] = []

    # Convenience shortcuts populated from the photos list for easy UI binding
    photo_plate_url: Optional[str] = None
    photo_odometer_url: Optional[str] = None
    photo_receipt_url: Optional[str] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_m: Optional[float] = None
    distance_from_pump_m: Optional[float] = None
    is_location_verified: bool

    status: str
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime

    # Display names for UI
    vehicle_number: Optional[str] = None
    petrol_pump_name: Optional[str] = None
    operator_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

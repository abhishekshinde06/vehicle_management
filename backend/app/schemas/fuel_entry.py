import math
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator


class UploadedPhotoResponse(BaseModel):
    id: str
    photo_id: str
    photo_type: str
    photo_url: str
    storage_type: str
    is_used: bool
    size_bytes: int
    content_type: str
    created_at: datetime


# Schema for an individual attached photo in a fuel entry
class EntryPhotoBase(BaseModel):
    photo_type: str = Field(
        ...,
        pattern="^(PLATE|ODOMETER|RECEIPT)$",
        description="Type of photo: PLATE, ODOMETER, or RECEIPT",
    )
    photo_url: str = Field(
        ...,
        min_length=1,
        description="Authenticated retrieval URL for the photo",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("photo_url")
    @classmethod
    def validate_photo_url_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Photo URL cannot be empty or blank")
        return v.strip()


class EntryPhotoCreate(BaseModel):
    photo_type: str = Field(
        ...,
        pattern="^(PLATE|ODOMETER|RECEIPT)$",
        description="Type of photo: PLATE, ODOMETER, or RECEIPT",
    )
    photo_id: Optional[str] = Field(
        default=None,
        description="UUID of the uploaded photo returned by /upload-photo",
    )
    photo_url: Optional[str] = Field(
        default=None,
        description="Authenticated retrieval URL returned by /upload-photo",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("photo_url")
    @classmethod
    def validate_photo_url_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Photo URL cannot be empty or blank")
        return stripped

    @field_validator("photo_id")
    @classmethod
    def validate_photo_id_not_blank(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        if not stripped:
            raise ValueError("Photo ID cannot be empty or blank")
        return stripped

    @model_validator(mode="after")
    def validate_photo_reference_present(self):
        if self.photo_id is None and self.photo_url is None:
            raise ValueError("Either photo_id or photo_url must be provided")
        return self


class EntryPhotoResponse(EntryPhotoBase):
    id: str
    uploaded_photo_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="ignore")


# Schema for creating a new fuel entry
class FuelEntryCreate(BaseModel):
    vehicle_id: str
    petrol_pump_id: str
    current_odometer: float = Field(
        ..., gt=0, allow_inf_nan=False, description="Current odometer reading"
    )
    fuel_litres: float = Field(
        ..., gt=0, allow_inf_nan=False, description="Fuel filled in litres"
    )
    is_full_tank: bool = Field(
        default=True, description="True if filled to full tank"
    )

    # List of attached photos (stored in entry_photos table)
    photos: List[EntryPhotoCreate] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly three photos: PLATE, ODOMETER, RECEIPT",
    )

    # GPS coordinates for geofencing check
    latitude: float = Field(..., ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(..., ge=-180, le=180, allow_inf_nan=False)
    accuracy_m: float = Field(..., ge=0, allow_inf_nan=False)

    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "current_odometer",
        "fuel_litres",
        "accuracy_m",
        "latitude",
        "longitude",
        mode="before",
    )
    @classmethod
    def validate_finite_numbers(cls, v):
        if isinstance(v, (int, float)) and not math.isfinite(v):
            raise ValueError("Numeric value must be finite (not NaN or Inf)")
        return v

    @model_validator(mode="after")
    def validate_required_photos(self):
        """
        Ensure all three required photo types are provided exactly once,
        with non-empty and non-duplicate references.
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
        photo_ids = []
        for photo in self.photos:
            if photo.photo_url is not None:
                stripped_url = photo.photo_url.strip()
                if not stripped_url:
                    raise ValueError("Photo URL cannot be empty")
                urls.append(stripped_url)
            if photo.photo_id is not None:
                stripped_id = photo.photo_id.strip()
                if not stripped_id:
                    raise ValueError("Photo ID cannot be empty")
                photo_ids.append(stripped_id)

        if len(set(urls)) != len(urls):
            raise ValueError("Duplicate photo URLs are not allowed")

        if len(set(photo_ids)) != len(photo_ids):
            raise ValueError("Duplicate photo IDs are not allowed")

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

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# Schema for an individual attached photo
class EntryPhotoBase(BaseModel):
    photo_type: str = Field(..., pattern="^(PLATE|ODOMETER|RECEIPT)$", description="Type of photo: PLATE, ODOMETER, or RECEIPT")
    photo_url: str = Field(..., description="Storage URL or relative path to the image")


class EntryPhotoCreate(EntryPhotoBase):
    pass


class EntryPhotoResponse(EntryPhotoBase):
    id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schema for creating a new fuel entry
class FuelEntryCreate(BaseModel):
    vehicle_id: str
    petrol_pump_id: str
    current_odometer: float = Field(..., gt=0, description="Current odometer reading")
    fuel_litres: float = Field(..., gt=0, description="Fuel filled in litres")
    is_full_tank: bool = Field(default=True, description="True if filled to full tank")

    # List of attached photos (stored in entry_photos table)
    photos: Optional[List[EntryPhotoCreate]] = []

    # Optional direct photo URLs (for backward compatibility / quick input)
    photo_plate_url: Optional[str] = None
    photo_odometer_url: Optional[str] = None
    photo_receipt_url: Optional[str] = None

    # GPS coordinates for geofencing check
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_m: Optional[float] = None


# Schema for Owner verification action
class FuelEntryVerify(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    rejection_reason: Optional[str] = None


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

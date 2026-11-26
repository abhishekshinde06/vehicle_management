"""
Fuel Entry & Mileage Tracking Routes
------------------------------------
Transactional API routes managing fueling entries and their attached media photos:
- POST  /api/fuel-entries: Submit a new fueling record with automatic mileage and photos.
- POST  /api/fuel-entries/upload-photo: Upload live photos (plate, odometer, receipt).
- GET   /api/fuel-entries: Query fueling logs with filters.
- GET   /api/fuel-entries/{id}: Retrieve full details of a specific fuel entry with photos.
- PATCH /api/fuel-entries/{id}/verify: Owner verification (Approve / Reject).
"""

import os
import math
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models import FuelEntry, Vehicle, PetrolPump, AuditLog, User, EntryPhoto
from app.schemas.fuel_entry import FuelEntryCreate, FuelEntryResponse, FuelEntryVerify
from app.routes.deps import get_current_user, get_current_operator, get_current_owner

router = APIRouter()


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates great-circle distance between two GPS coordinates in meters.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


@router.post("/upload-photo", summary="Upload Live Camera Photo")
async def upload_photo(
    file: UploadFile = File(..., description="Image file to upload (JPEG, PNG, WebP)"),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads a photo (e.g. License Plate, Odometer, or Receipt) to server storage.
    Returns the static URL path for attaching to fuel entries.
    """
    allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
    ext = os.path.splitext(file.filename)[1].lower() if file.filename else ".jpg"
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed: {', '.join(sorted(allowed_extensions))}"
        )

    filename = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    return {
        "filename": filename,
        "photo_url": f"/uploads/{filename}",
        "size_bytes": len(contents),
        "content_type": file.content_type
    }


@router.post("/", response_model=FuelEntryResponse, status_code=status.HTTP_201_CREATED, summary="Submit Fuel Entry")
def create_fuel_entry(
    entry_in: FuelEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_operator)
):
    """
    Submits a new vehicle fueling record and stores attached photos in the `entry_photos` table.

    Business Rules:
    1. Checks vehicle exists and is active.
    2. Checks petrol pump exists and is active.
    3. Retrieves previous odometer reading.
    4. Validates that current odometer > previous odometer (rejects lower readings).
    5. Calculates distance: `current_odometer - previous_odometer`.
    6. Calculates mileage: `distance / fuel_litres` (for full tank refills).
    7. Validates GPS coordinates against authorized petrol pump geofence radius.
    8. Creates `FuelEntry` and associated `EntryPhoto` records.
    9. Records audit log for traceability.
    """
    # 1. Verify Vehicle
    vehicle = db.query(Vehicle).filter(Vehicle.id == entry_in.vehicle_id, Vehicle.is_active == True).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found or inactive")

    # 2. Verify Petrol Pump
    pump = db.query(PetrolPump).filter(PetrolPump.id == entry_in.petrol_pump_id, PetrolPump.is_active == True).first()
    if not pump:
        raise HTTPException(status_code=404, detail="Authorized petrol pump not found")

    # 3. Retrieve previous odometer reading
    latest_entry = (
        db.query(FuelEntry)
        .filter(FuelEntry.vehicle_id == vehicle.id, FuelEntry.status != "REJECTED")
        .order_by(FuelEntry.created_at.desc(), FuelEntry.id.desc())
        .first()
    )
    previous_odometer = latest_entry.current_odometer if latest_entry else vehicle.initial_odometer

    # 4. Strict Validation: Current odometer must be greater than previous
    if entry_in.current_odometer <= previous_odometer:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid odometer reading! Current ({entry_in.current_odometer} km) must be greater than previous ({previous_odometer} km)."
        )

    # 5. Mileage & Distance Computation
    distance_km = round(entry_in.current_odometer - previous_odometer, 2)
    mileage_kmpl = None
    if entry_in.is_full_tank and entry_in.fuel_litres > 0:
        mileage_kmpl = round(distance_km / entry_in.fuel_litres, 2)

    # 6. Geofence & Location Validation (if coordinates provided)
    distance_from_pump = None
    is_location_verified = True
    if entry_in.latitude is not None and entry_in.longitude is not None:
        distance_from_pump = round(
            calculate_haversine_distance(
                entry_in.latitude,
                entry_in.longitude,
                pump.latitude,
                pump.longitude
            ),
            1
        )
        allowed_radius = pump.radius_meters or settings.DEFAULT_GEOFENCE_RADIUS_METERS
        is_location_verified = distance_from_pump <= allowed_radius

    # 7. Save Core Fuel Entry
    new_entry = FuelEntry(
        vehicle_id=vehicle.id,
        petrol_pump_id=pump.id,
        operator_id=current_user.id,
        current_odometer=entry_in.current_odometer,
        previous_odometer=previous_odometer,
        fuel_litres=entry_in.fuel_litres,
        is_full_tank=entry_in.is_full_tank,
        distance_km=distance_km,
        mileage_kmpl=mileage_kmpl,
        latitude=entry_in.latitude,
        longitude=entry_in.longitude,
        accuracy_m=entry_in.accuracy_m,
        distance_from_pump_m=distance_from_pump,
        is_location_verified=is_location_verified,
        status="PENDING"
    )
    db.add(new_entry)
    db.flush()  # Generates new_entry.id

    # 8. Collect and Save Attached Photos in entry_photos table
    photos_to_add = []
    # Add from photos list if provided
    if entry_in.photos:
        for p in entry_in.photos:
            photos_to_add.append(EntryPhoto(
                fuel_entry_id=new_entry.id,
                photo_type=p.photo_type,
                photo_url=p.photo_url
            ))
    
    # Also support direct fields if provided
    if entry_in.photo_plate_url:
        photos_to_add.append(EntryPhoto(fuel_entry_id=new_entry.id, photo_type="PLATE", photo_url=entry_in.photo_plate_url))
    if entry_in.photo_odometer_url:
        photos_to_add.append(EntryPhoto(fuel_entry_id=new_entry.id, photo_type="ODOMETER", photo_url=entry_in.photo_odometer_url))
    if entry_in.photo_receipt_url:
        photos_to_add.append(EntryPhoto(fuel_entry_id=new_entry.id, photo_type="RECEIPT", photo_url=entry_in.photo_receipt_url))

    if photos_to_add:
        db.add_all(photos_to_add)

    # 9. Record Audit Log
    log = AuditLog(
        fuel_entry_id=new_entry.id,
        action="CREATED",
        performed_by=current_user.id,
        remarks=f"Fuel entry recorded by '{current_user.username}' for vehicle '{vehicle.vehicle_number}' with {len(photos_to_add)} photo(s)"
    )
    db.add(log)
    try:
        db.commit()
        db.refresh(new_entry)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to record fuel entry due to a duplicate conflict or database constraint violation. Please verify entry details."
        )

    return _format_entry_response(new_entry, vehicle, pump, current_user)


@router.get("/", response_model=List[FuelEntryResponse], summary="List Fuel Entries")
def list_fuel_entries(
    vehicle_id: Optional[str] = Query(None, description="Filter by Vehicle ID"),
    status: Optional[str] = Query(None, description="Filter by Status: PENDING, APPROVED, REJECTED"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns fuel entries sorted by latest first, with optional filters.
    Includes related photos from the `entry_photos` table.
    """
    query = db.query(FuelEntry).order_by(FuelEntry.created_at.desc())
    if vehicle_id:
        query = query.filter(FuelEntry.vehicle_id == vehicle_id)
    if status:
        query = query.filter(FuelEntry.status == status.upper())

    entries = query.all()
    results = []
    for entry in entries:
        results.append(_format_entry_response(entry, entry.vehicle, entry.petrol_pump, entry.operator))
    return results


@router.get("/{id}", response_model=FuelEntryResponse, summary="Get Fuel Entry Details")
def get_fuel_entry(id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetches details of a specific fuel entry by ID, including all attached photos.
    """
    entry = db.query(FuelEntry).filter(FuelEntry.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Fuel entry not found")
    return _format_entry_response(entry, entry.vehicle, entry.petrol_pump, entry.operator)


@router.patch("/{id}/verify", response_model=FuelEntryResponse, summary="Approve or Reject Entry")
def verify_fuel_entry(
    id: str,
    verify_in: FuelEntryVerify,
    db: Session = Depends(get_db),
    owner: User = Depends(get_current_owner)
):
    """
    Allows the Owner to Approve or Reject a fuel entry.
    Records the decision in the audit log.
    """
    entry = db.query(FuelEntry).filter(FuelEntry.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Fuel entry not found")

    entry.status = verify_in.status
    entry.rejection_reason = verify_in.rejection_reason if verify_in.status == "REJECTED" else None
    entry.reviewed_by = owner.id
    entry.reviewed_at = datetime.now(timezone.utc)

    log = AuditLog(
        fuel_entry_id=entry.id,
        action=verify_in.status,
        performed_by=owner.id,
        remarks=f"Marked as {verify_in.status} by owner '{owner.username}'. Reason: {verify_in.rejection_reason or 'None'}"
    )
    db.add(log)
    db.commit()
    db.refresh(entry)

    return _format_entry_response(entry, entry.vehicle, entry.petrol_pump, entry.operator)


def _format_entry_response(entry: FuelEntry, vehicle: Vehicle, pump: PetrolPump, operator: User) -> dict:
    """
    Serializes a FuelEntry model with populated vehicle number, pump name, operator name,
    and attached photos from the `entry_photos` table.
    """
    # Extract photos list and convenience URLs
    photos_data = []
    plate_url = None
    odometer_url = None
    receipt_url = None

    if entry.photos:
        for p in entry.photos:
            photos_data.append({
                "id": p.id,
                "photo_type": p.photo_type,
                "photo_url": p.photo_url,
                "created_at": p.created_at
            })
            if p.photo_type == "PLATE" and not plate_url:
                plate_url = p.photo_url
            elif p.photo_type == "ODOMETER" and not odometer_url:
                odometer_url = p.photo_url
            elif p.photo_type == "RECEIPT" and not receipt_url:
                receipt_url = p.photo_url

    return {
        "id": entry.id,
        "vehicle_id": entry.vehicle_id,
        "petrol_pump_id": entry.petrol_pump_id,
        "operator_id": entry.operator_id,
        "current_odometer": entry.current_odometer,
        "previous_odometer": entry.previous_odometer,
        "fuel_litres": entry.fuel_litres,
        "is_full_tank": entry.is_full_tank,
        "distance_km": entry.distance_km,
        "mileage_kmpl": entry.mileage_kmpl,
        "photos": photos_data,
        "photo_plate_url": plate_url,
        "photo_odometer_url": odometer_url,
        "photo_receipt_url": receipt_url,
        "latitude": entry.latitude,
        "longitude": entry.longitude,
        "accuracy_m": entry.accuracy_m,
        "distance_from_pump_m": entry.distance_from_pump_m,
        "is_location_verified": entry.is_location_verified,
        "status": entry.status,
        "rejection_reason": entry.rejection_reason,
        "reviewed_by": entry.reviewed_by,
        "reviewed_at": entry.reviewed_at,
        "created_at": entry.created_at,
        "vehicle_number": vehicle.vehicle_number if vehicle else None,
        "petrol_pump_name": pump.name if pump else None,
        "operator_name": operator.full_name or operator.username if operator else None,
    }

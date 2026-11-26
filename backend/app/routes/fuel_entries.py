"""
Fuel Entry & Mileage Tracking Routes
------------------------------------
Transactional API routes managing fueling entries and authenticated photo storage:
- POST  /api/fuel-entries/upload-photo: Validate & store live photo (plate, odometer, receipt).
- GET   /api/fuel-entries/photos/{photo_id}: Authenticated photo retrieval (owner all, operator own).
- POST  /api/fuel-entries: Submit a new fueling record with automatic mileage and validated photos.
- GET   /api/fuel-entries: Query fueling logs with filters.
- GET   /api/fuel-entries/{id}: Retrieve full details of a specific fuel entry with photos.
- PATCH /api/fuel-entries/{id}/verify: Owner verification (Approve / Reject).
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.geofence import calculate_distance_m, verify_geofence
from app.core.mileage import calculate_mileage
from app.models import FuelEntry, Vehicle, PetrolPump, AuditLog, User, EntryPhoto, UploadedPhoto
from app.routes.deps import get_current_user, get_current_operator, get_current_owner
from app.schemas.fuel_entry import (
    EntryPhotoCreate,
    FuelEntryCreate,
    FuelEntryResponse,
    FuelEntryVerify,
    UploadedPhotoResponse,
)
from app.schemas.geofence import GeofenceVerifyRequest
from app.services.storage import (
    ImageTooLargeError,
    ImageValidationError,
    PhotoNotFoundError,
    StorageError,
    delete_image,
    get_viewable_url,
    read_image,
    save_image,
    validate_image_bytes,
)

router = APIRouter()

VALID_PHOTO_TYPES = {"PLATE", "ODOMETER", "RECEIPT"}


def _build_photo_retrieval_url(photo_id: str) -> str:
    prefix = settings.API_PREFIX.rstrip("/")
    return f"{prefix}/fuel-entries/photos/{photo_id}"


def _extract_uploaded_photo_id(photo_in: EntryPhotoCreate) -> str:
    expected_prefix = f"{settings.API_PREFIX.rstrip('/')}/fuel-entries/photos/"
    url_photo_id: Optional[str] = None

    if photo_in.photo_url is not None:
        url = photo_in.photo_url.strip()
        if not url.startswith(expected_prefix):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid photo reference. Photos must be uploaded via /api/fuel-entries/upload-photo.",
            )
        candidate = url[len(expected_prefix):].strip("/")
        if not candidate or "/" in candidate or ".." in candidate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid photo reference URL.",
            )
        url_photo_id = candidate

    if photo_in.photo_id is not None:
        explicit_id = photo_in.photo_id.strip()
        if url_photo_id is not None and explicit_id != url_photo_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="photo_id does not match photo_url.",
            )
        return explicit_id

    if url_photo_id is not None:
        return url_photo_id

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Photo reference is required.",
    )


@router.post(
    "/upload-photo",
    response_model=UploadedPhotoResponse,
    summary="Upload Live Camera Photo",
)
async def upload_photo(
    photo_type: str = Form(..., description="Photo type: PLATE, ODOMETER, or RECEIPT"),
    file: UploadFile = File(..., description="Image file to upload (JPEG, PNG, WebP; max 5 MB)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_operator),
):
    """
    Validates image bytes with Pillow (rejects empty, oversized >5 MB, corrupted, or
    unsupported files), stores the image in local disk or configured S3 storage, and
    tracks the upload in `uploaded_photos` bound to the authenticated uploader.
    """
    normalized_type = photo_type.strip().upper() if photo_type else ""
    if normalized_type not in VALID_PHOTO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid photo_type. Must be one of: PLATE, ODOMETER, RECEIPT.",
        )

    contents = await file.read(settings.MAX_IMAGE_SIZE_BYTES + 1)

    try:
        ext, content_type = validate_image_bytes(contents, settings.MAX_IMAGE_SIZE_BYTES)
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except ImageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    photo_id = str(uuid.uuid4())
    filename = f"{photo_id}{ext}"

    try:
        saved = save_image(contents=contents, filename=filename, content_type=content_type)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    uploaded_photo = UploadedPhoto(
        id=photo_id,
        uploader_id=current_user.id,
        photo_type=normalized_type,
        storage_type=saved["storage_type"],
        storage_reference=saved["storage_reference"],
        content_type=saved["content_type"],
        size_bytes=saved["size_bytes"],
        is_used=False,
    )

    try:
        db.add(uploaded_photo)
        db.commit()
        db.refresh(uploaded_photo)
    except Exception as exc:
        db.rollback()
        delete_image(saved["storage_reference"], saved["storage_type"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register uploaded photo.",
        ) from exc

    return {
        "id": uploaded_photo.id,
        "photo_id": uploaded_photo.id,
        "photo_type": uploaded_photo.photo_type,
        "photo_url": _build_photo_retrieval_url(uploaded_photo.id),
        "storage_type": uploaded_photo.storage_type,
        "is_used": uploaded_photo.is_used,
        "size_bytes": uploaded_photo.size_bytes,
        "content_type": uploaded_photo.content_type,
        "created_at": uploaded_photo.created_at,
    }


@router.get("/photos/{photo_id}", summary="Retrieve Authenticated Fuel Entry Photo")
def get_photo(
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Serves a stored fuel entry photo with strict authentication and RBAC:
    - Owners can retrieve any photo.
    - Operators can retrieve only photos belonging to their own uploads/fuel entries.
    """
    uploaded = db.query(UploadedPhoto).filter(UploadedPhoto.id == photo_id).first()

    if uploaded is None:
        entry_photo = db.query(EntryPhoto).filter(EntryPhoto.id == photo_id).first()
        if entry_photo is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

        if current_user.role != "owner":
            if entry_photo.fuel_entry is None or entry_photo.fuel_entry.operator_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. Operators can only view their own fuel entry photos.",
                )

        if entry_photo.uploaded_photo_id:
            uploaded = (
                db.query(UploadedPhoto)
                .filter(UploadedPhoto.id == entry_photo.uploaded_photo_id)
                .first()
            )
        if uploaded is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    else:
        if current_user.role != "owner":
            if uploaded.fuel_entry_id:
                linked_entry = (
                    db.query(FuelEntry)
                    .filter(FuelEntry.id == uploaded.fuel_entry_id)
                    .first()
                )
                if linked_entry is None or linked_entry.operator_id != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied. Operators can only view their own fuel entry photos.",
                    )
            elif uploaded.uploader_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. Operators can only view their own fuel entry photos.",
                )

    try:
        image_bytes = read_image(uploaded.storage_reference, uploaded.storage_type)
    except PhotoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return Response(
        content=image_bytes,
        media_type=uploaded.content_type,
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/", response_model=FuelEntryResponse, status_code=status.HTTP_201_CREATED, summary="Submit Fuel Entry")
def create_fuel_entry(
    entry_in: FuelEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_operator),
):
    """
    Submits a new vehicle fueling record and stores attached photos in the `entry_photos` table.

    Business Rules:
    1. Checks vehicle exists and is active.
    2. Checks petrol pump exists and is active.
    3. Validates GPS coordinates against the authorized petrol pump geofence.
    4. Validates that current odometer > previous odometer.
    5. Calculates distance and full-to-full mileage including intermediate partial refills.
    6. Validates that all three uploaded photos exist, belong to the authenticated
       operator, match the required photo types, and have not already been used,
       with database-level protection against concurrent reuse.
    7. Creates `FuelEntry`, `EntryPhoto`, and `AuditLog` records atomically.
    """
    # 1. Verify Vehicle
    vehicle = (
        db.query(Vehicle)
        .filter(
            Vehicle.id == entry_in.vehicle_id,
            Vehicle.is_active.is_(True),
        )
        .with_for_update()
        .first()
    )

    if not vehicle:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found or inactive",
        )

    # 2. Verify Petrol Pump
    pump = (
        db.query(PetrolPump)
        .filter(PetrolPump.id == entry_in.petrol_pump_id, PetrolPump.is_active == True)  # noqa: E712
        .first()
    )
    if not pump:
        raise HTTPException(status_code=404, detail="Authorized petrol pump not found")

    if (
        entry_in.latitude is None
        or entry_in.longitude is None
        or entry_in.accuracy_m is None
    ):
        raise HTTPException(
            status_code=400,
            detail="GPS latitude, longitude and accuracy are required",
        )

    is_verified = verify_geofence(
        operator_lat=entry_in.latitude,
        operator_lon=entry_in.longitude,
        pump_lat=pump.latitude,
        pump_lon=pump.longitude,
        gps_accuracy=entry_in.accuracy_m,
        radius=pump.radius_meters,
    )

    if not is_verified:
        raise HTTPException(
            status_code=403,
            detail="GPS verification failed. Please be within the authorized petrol pump radius with accurate GPS.",
        )

    distance_from_pump = calculate_distance_m(
        entry_in.latitude,
        entry_in.longitude,
        pump.latitude,
        pump.longitude,
    )

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
            detail=f"Invalid odometer reading! Current ({entry_in.current_odometer} km) must be greater than previous ({previous_odometer} km).",
        )

    # 5. Resolve and lock uploaded photos in deterministic ID order to prevent race conditions
    resolved_items = [(p, _extract_uploaded_photo_id(p)) for p in entry_in.photos]
    resolved_ids = [item[1] for item in resolved_items]
    if len(set(resolved_ids)) != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Three distinct uploaded photos are required.",
        )

    locked_photos = (
        db.query(UploadedPhoto)
        .filter(UploadedPhoto.id.in_(sorted(resolved_ids)))
        .order_by(UploadedPhoto.id.asc())
        .with_for_update()
        .all()
    )
    photo_map = {photo.id: photo for photo in locked_photos}

    for photo_in, resolved_id in resolved_items:
        uploaded = photo_map.get(resolved_id)
        if uploaded is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Uploaded photo '{resolved_id}' not found.",
            )
        if uploaded.uploader_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Attached photos must belong to the authenticated operator.",
            )
        if uploaded.photo_type != photo_in.photo_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Photo '{resolved_id}' has type '{uploaded.photo_type}', expected '{photo_in.photo_type}'.",
            )
        if uploaded.is_used:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Photo '{resolved_id}' has already been used in another fuel entry.",
            )

    # 6. Mileage & Distance Computation
    distance_km = round(entry_in.current_odometer - previous_odometer, 2)
    mileage_kmpl = None

    if entry_in.is_full_tank:
        previous_full_entry = (
            db.query(FuelEntry)
            .filter(
                FuelEntry.vehicle_id == vehicle.id,
                FuelEntry.is_full_tank.is_(True),
                FuelEntry.status != "REJECTED",
            )
            .order_by(FuelEntry.current_odometer.desc())
            .first()
        )

        if previous_full_entry:
            partial_fuel = (
                db.query(func.sum(FuelEntry.fuel_litres))
                .filter(
                    FuelEntry.vehicle_id == vehicle.id,
                    FuelEntry.is_full_tank.is_(False),
                    FuelEntry.status != "REJECTED",
                    FuelEntry.current_odometer > previous_full_entry.current_odometer,
                    FuelEntry.current_odometer < entry_in.current_odometer,
                )
                .scalar()
            ) or 0.0

            mileage_kmpl = calculate_mileage(
                previous_full_odometer=previous_full_entry.current_odometer,
                current_odometer=entry_in.current_odometer,
                current_fuel_litres=entry_in.fuel_litres,
                partial_fuel_litres=partial_fuel,
                is_full_tank=True,
            )

    # 7. Save Core Fuel Entry & atomically claim uploaded photos
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
        distance_from_pump_m=round(distance_from_pump, 2),
        is_location_verified=is_verified,
        status="PENDING",
    )

    try:
        db.add(new_entry)
        db.flush()  # Generates new_entry.id

        now_utc = datetime.now(timezone.utc)
        photos_to_add = []
        for photo_in, resolved_id in resolved_items:
            updated_rows = (
                db.query(UploadedPhoto)
                .filter(
                    UploadedPhoto.id == resolved_id,
                    UploadedPhoto.is_used.is_(False),
                )
                .update(
                    {
                        UploadedPhoto.is_used: True,
                        UploadedPhoto.fuel_entry_id: new_entry.id,
                        UploadedPhoto.used_at: now_utc,
                    },
                    synchronize_session=False,
                )
            )
            if updated_rows != 1:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Photo '{resolved_id}' has already been used in another fuel entry.",
                )

            photos_to_add.append(
                EntryPhoto(
                    fuel_entry_id=new_entry.id,
                    uploaded_photo_id=resolved_id,
                    photo_type=photo_in.photo_type,
                    photo_url=_build_photo_retrieval_url(resolved_id),
                )
            )

        db.add_all(photos_to_add)

        log = AuditLog(
            fuel_entry_id=new_entry.id,
            action="CREATED",
            performed_by=current_user.id,
            remarks=f"Fuel entry recorded by '{current_user.username}' for vehicle '{vehicle.vehicle_number}' with {len(photos_to_add)} photo(s)",
        )
        db.add(log)
        db.commit()
        db.refresh(new_entry)
    except HTTPException:
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more photos have already been used in another fuel entry.",
        ) from exc

    return _format_entry_response(new_entry, vehicle, pump, current_user)


@router.get("/", response_model=List[FuelEntryResponse], summary="List Fuel Entries")
def list_fuel_entries(
    vehicle_id: Optional[str] = Query(None, description="Filter by Vehicle ID"),
    petrol_pump_id: Optional[str] = Query(None, description="Filter by Petrol Pump ID"),
    status: Optional[str] = Query(None, description="Filter by Status: PENDING, APPROVED, REJECTED"),
    start_date: Optional[datetime] = Query(None, description="Filter entries created on or after this date"),
    end_date: Optional[datetime] = Query(None, description="Filter entries created on or before this date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns fuel entries sorted by latest first, with optional filters.
    Includes related photos from the `entry_photos` table.
    Enforces authorization:
    - Owners can view all fuel entries.
    - Operators can view only their own fuel entries.
    """
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="Invalid date range: start_date must be before or equal to end_date",
        )

    query = db.query(FuelEntry).order_by(FuelEntry.created_at.desc(), FuelEntry.id.desc())

    # RBAC: Operators can view only their own fuel entries; Owners can view all
    if current_user.role != "owner":
        query = query.filter(FuelEntry.operator_id == current_user.id)

    if vehicle_id:
        query = query.filter(FuelEntry.vehicle_id == vehicle_id)
    if petrol_pump_id:
        query = query.filter(FuelEntry.petrol_pump_id == petrol_pump_id)
    if status:
        query = query.filter(FuelEntry.status == status.upper())
    if start_date:
        query = query.filter(FuelEntry.created_at >= start_date.replace(tzinfo=None))
    if end_date:
        clean_end = end_date.replace(tzinfo=None)
        if clean_end.hour == 0 and clean_end.minute == 0 and clean_end.second == 0 and clean_end.microsecond == 0:
            clean_end = clean_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        query = query.filter(FuelEntry.created_at <= clean_end)

    entries = query.all()
    results = []
    for entry in entries:
        results.append(_format_entry_response(entry, entry.vehicle, entry.petrol_pump, entry.operator))
    return results


@router.get("/{id}", response_model=FuelEntryResponse, summary="Get Fuel Entry Details")
def get_fuel_entry(id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetches details of a specific fuel entry by ID, including all attached photos.
    Enforces authorization:
    - Owners can view any fuel entry.
    - Operators can view only their own fuel entries.
    """
    entry = db.query(FuelEntry).filter(FuelEntry.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Fuel entry not found")

    if current_user.role != "owner" and entry.operator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Operators can only view their own fuel entries.",
        )

    return _format_entry_response(entry, entry.vehicle, entry.petrol_pump, entry.operator)


@router.patch("/{id}/verify", response_model=FuelEntryResponse, summary="Approve or Reject Entry")
def verify_fuel_entry(
    id: str,
    verify_in: FuelEntryVerify,
    db: Session = Depends(get_db),
    owner: User = Depends(get_current_owner),
):
    """
    Allows the Owner to Approve or Reject a fuel entry.
    Records the decision in the audit log.
    """
    entry = db.query(FuelEntry).filter(FuelEntry.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Fuel entry not found")
    # Prevent repeated verification.
    db.query(Vehicle).filter(Vehicle.id == entry.vehicle_id).with_for_update().one()

    db.refresh(entry)
    if entry.status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="Fuel entry has already been reviewed",
        )

    # Rejection reason is mandatory.
    if verify_in.status == "REJECTED":
        if not verify_in.rejection_reason or not verify_in.rejection_reason.strip():
            raise HTTPException(
                status_code=400,
                detail="Rejection reason is required",
            )
    entry.status = verify_in.status
    entry.rejection_reason = verify_in.rejection_reason if verify_in.status == "REJECTED" else None
    entry.reviewed_by = owner.id
    entry.reviewed_at = datetime.now(timezone.utc)

    log = AuditLog(
        fuel_entry_id=entry.id,
        action=verify_in.status,
        performed_by=owner.id,
        remarks=f"Marked as {verify_in.status} by owner '{owner.username}'. Reason: {verify_in.rejection_reason or 'None'}",
    )
    db.add(log)

    if entry.status == "REJECTED":
        entry.mileage_kmpl = None
        db.flush()
        recalculate_vehicle_mileage(db, entry.vehicle_id)

    db.commit()
    db.refresh(entry)

    return _format_entry_response(entry, entry.vehicle, entry.petrol_pump, entry.operator)


def recalculate_vehicle_mileage(db: Session, vehicle_id: str):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()

    entries = (
        db.query(FuelEntry)
        .filter(
            FuelEntry.vehicle_id == vehicle_id,
            FuelEntry.status != "REJECTED",
        )
        .order_by(FuelEntry.current_odometer.asc())
        .all()
    )

    previous_odometer = vehicle.initial_odometer
    previous_full_odometer = None
    partial_fuel = 0.0

    for entry in entries:
        entry.previous_odometer = previous_odometer
        entry.distance_km = round(entry.current_odometer - previous_odometer, 2)
        entry.mileage_kmpl = None

        if entry.is_full_tank:
            if previous_full_odometer is not None:
                entry.mileage_kmpl = calculate_mileage(
                    previous_full_odometer=previous_full_odometer,
                    current_odometer=entry.current_odometer,
                    current_fuel_litres=entry.fuel_litres,
                    partial_fuel_litres=partial_fuel,
                )

            previous_full_odometer = entry.current_odometer
            partial_fuel = 0.0

        elif previous_full_odometer is not None:
            partial_fuel += entry.fuel_litres

        previous_odometer = entry.current_odometer


def _format_entry_response(entry: FuelEntry, vehicle: Vehicle, pump: PetrolPump, operator: User) -> dict:
    """
    Serializes a FuelEntry model with populated vehicle number, pump name, operator name,
    and attached photos pointing to the authenticated retrieval endpoint.
    """
    photos_data = []
    plate_url = None
    odometer_url = None
    receipt_url = None

    if entry.photos:
        for p in entry.photos:
            raw_url = (
                _build_photo_retrieval_url(p.uploaded_photo_id)
                if p.uploaded_photo_id
                else p.photo_url
            )
            viewable_url = get_viewable_url(raw_url)
            photos_data.append({
                "id": p.id,
                "uploaded_photo_id": p.uploaded_photo_id,
                "photo_type": p.photo_type,
                "photo_url": viewable_url,
                "created_at": p.created_at,
            })
            if p.photo_type == "PLATE" and not plate_url:
                plate_url = viewable_url
            elif p.photo_type == "ODOMETER" and not odometer_url:
                odometer_url = viewable_url
            elif p.photo_type == "RECEIPT" and not receipt_url:
                receipt_url = viewable_url

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


@router.post("/verify-location")
def verify_location(
    data: GeofenceVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_operator),
):
    pump = db.query(PetrolPump).filter(
        PetrolPump.id == data.petrol_pump_id,
        PetrolPump.is_active.is_(True),
    ).first()

    if not pump:
        raise HTTPException(
            status_code=404,
            detail="Authorized petrol pump not found",
        )

    is_verified = verify_geofence(
        data.latitude,
        data.longitude,
        pump.latitude,
        pump.longitude,
        data.accuracy_m,
        pump.radius_meters,
    )

    if not is_verified:
        raise HTTPException(
            status_code=403,
            detail="Outside authorized area or insufficient GPS accuracy",
        )

    distance = calculate_distance_m(
        data.latitude,
        data.longitude,
        pump.latitude,
        pump.longitude,
    )

    return {
        "is_location_verified": True,
        "petrol_pump_id": pump.id,
        "petrol_pump_name": pump.name,
        "distance_from_pump_m": round(distance, 2),
        "message": "Location verified. Camera capture allowed.",
    }

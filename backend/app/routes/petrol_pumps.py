"""
Authorized Petrol Pump Routes
-----------------------------
Routes for querying and registering authorized petrol pumps:
- GET  /api/petrol-pumps
- POST /api/petrol-pumps (Owner only)
"""

import math
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import PetrolPump
from app.schemas.petrol_pump import PetrolPumpResponse, PetrolPumpCreate
from app.routes.deps import get_current_user, get_current_owner

router = APIRouter()

# Threshold: If another active pump is within this distance in meters, reject as duplicate location
MIN_PUMP_DISTANCE_METERS = 50.0


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


@router.get("/", response_model=List[PetrolPumpResponse], summary="List Authorized Petrol Pumps")
def list_petrol_pumps(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Returns all authorized petrol pumps with their location coordinates and geofence radius.
    """
    return db.query(PetrolPump).filter(PetrolPump.is_active == True).all()


@router.post("/", response_model=PetrolPumpResponse, status_code=status.HTTP_201_CREATED, summary="Register Petrol Pump")
def create_petrol_pump(
    pump_in: PetrolPumpCreate,
    db: Session = Depends(get_db),
    owner = Depends(get_current_owner)
):
    """
    Registers an authorized petrol pump location where fueling is permitted.
    Restricted to Owners.
    Prevents duplicate names and duplicate physical locations using distance-based validation.
    """
    cleaned_name = pump_in.name.strip()

    # 1. Application-level check for duplicate name (case-insensitive)
    existing_name = db.query(PetrolPump).filter(
        func.lower(PetrolPump.name) == cleaned_name.lower(),
        PetrolPump.is_active == True
    ).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Petrol pump with name '{cleaned_name}' is already registered."
        )

    # 2. Distance-based duplicate location validation:
    # Query nearby candidate pumps and compute great-circle distance (Haversine formula).
    # Rejects if another active pump exists within MIN_PUMP_DISTANCE_METERS (e.g. 50 meters).
    # Latitude degree ~ 111km; 1000m ~ 0.01 degrees bounding box filter for DB efficiency:
    bbox_delta = 0.02
    nearby_pumps = db.query(PetrolPump).filter(
        PetrolPump.is_active == True,
        PetrolPump.latitude.between(pump_in.latitude - bbox_delta, pump_in.latitude + bbox_delta),
        PetrolPump.longitude.between(pump_in.longitude - bbox_delta, pump_in.longitude + bbox_delta)
    ).all()

    for p in nearby_pumps:
        distance = calculate_haversine_distance(pump_in.latitude, pump_in.longitude, p.latitude, p.longitude)
        if distance < MIN_PUMP_DISTANCE_METERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"A petrol pump ('{p.name}') already exists at this physical location "
                    f"({round(distance, 1)}m away). Minimum required separation is {MIN_PUMP_DISTANCE_METERS}m."
                )
            )

    pump_data = pump_in.model_dump()
    pump_data["name"] = cleaned_name
    pump = PetrolPump(**pump_data)
    db.add(pump)
    try:
        db.commit()
        db.refresh(pump)
    except IntegrityError as exc:
        db.rollback()
        err_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
        if "uq_petrol_pumps_lat_lon" in err_msg or "latitude" in err_msg or "longitude" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A petrol pump is already registered at these exact GPS coordinates."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Petrol pump with name '{cleaned_name}' already exists."
        )

    return pump

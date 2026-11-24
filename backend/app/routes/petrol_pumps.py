"""
Authorized Petrol Pump Routes
-----------------------------
Routes for querying and registering authorized petrol pumps:
- GET  /api/petrol-pumps
- POST /api/petrol-pumps (Owner only)
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import PetrolPump
from app.schemas.petrol_pump import PetrolPumpResponse, PetrolPumpCreate
from app.routes.deps import get_current_user, get_current_owner

router = APIRouter()


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
    Prevents duplicate names or duplicate GPS locations.
    """
    cleaned_name = pump_in.name.strip()

    # 1. Check for duplicate name (case-insensitive)
    existing_name = db.query(PetrolPump).filter(
        func.lower(PetrolPump.name) == cleaned_name.lower(),
        PetrolPump.is_active == True
    ).first()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Petrol pump with name '{cleaned_name}' is already registered."
        )

    # 2. Check for duplicate GPS coordinates (same location)
    existing_coords = db.query(PetrolPump).filter(
        PetrolPump.latitude == pump_in.latitude,
        PetrolPump.longitude == pump_in.longitude,
        PetrolPump.is_active == True
    ).first()
    if existing_coords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A petrol pump ('{existing_coords.name}') is already registered at these exact GPS coordinates."
        )

    pump_data = pump_in.model_dump()
    pump_data["name"] = cleaned_name
    pump = PetrolPump(**pump_data)
    db.add(pump)
    db.commit()
    db.refresh(pump)
    return pump

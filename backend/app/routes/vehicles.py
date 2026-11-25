"""
Vehicle Management Routes
-------------------------
Routes for querying fleet vehicles and their current odometer status:
- GET  /api/vehicles
- POST /api/vehicles (Owner only)
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import Vehicle, FuelEntry
from app.schemas.vehicle import VehicleResponse, VehicleCreate
from app.routes.deps import get_current_user, get_current_owner

router = APIRouter()


@router.get("/", response_model=List[VehicleResponse], summary="List Fleet Vehicles")
def list_vehicles(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    """
    Returns all active vehicles in the fleet.
    Calculates the latest verified odometer for each vehicle.
    """
    vehicles = db.query(Vehicle).filter(Vehicle.is_active == True).all()
    results = []
    for v in vehicles:
        latest_entry = (
            db.query(FuelEntry)
            .filter(FuelEntry.vehicle_id == v.id, FuelEntry.status != "REJECTED")
            .order_by(FuelEntry.created_at.desc())
            .first()
        )
        latest_odo = latest_entry.current_odometer if latest_entry else v.initial_odometer
        results.append({
            "id": v.id,
            "vehicle_number": v.vehicle_number,
            "model": v.model,
            "initial_odometer": v.initial_odometer,
            "latest_odometer": latest_odo,
            "is_active": v.is_active,
            "created_at": v.created_at,
        })
    return results


@router.post("/", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED, summary="Add Fleet Vehicle")
def create_vehicle(
    vehicle_in: VehicleCreate,
    db: Session = Depends(get_db),
    owner = Depends(get_current_owner)
):
    """
    Adds a new vehicle to the fleet with an initial odometer reading.
    Restricted to Owners.
    Handles duplicate vehicle number with database-level IntegrityError rollback.
    """
    # 1. Application-level check
    existing = db.query(Vehicle).filter(Vehicle.vehicle_number == vehicle_in.vehicle_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vehicle number already registered")

    vehicle = Vehicle(**vehicle_in.model_dump())
    db.add(vehicle)
    try:
        db.commit()
        db.refresh(vehicle)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vehicle with number '{vehicle_in.vehicle_number}' already exists."
        )

    return {
        "id": vehicle.id,
        "vehicle_number": vehicle.vehicle_number,
        "model": vehicle.model,
        "initial_odometer": vehicle.initial_odometer,
        "latest_odometer": vehicle.initial_odometer,
        "is_active": vehicle.is_active,
        "created_at": vehicle.created_at,
    }

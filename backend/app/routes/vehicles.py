"""
Vehicle Management Routes
-------------------------
Routes for querying fleet vehicles and their current odometer status:
- GET  /api/vehicles
- POST /api/vehicles (Owner only)
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
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
    """
    existing = db.query(Vehicle).filter(Vehicle.vehicle_number == vehicle_in.vehicle_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vehicle number already registered")

    vehicle = Vehicle(**vehicle_in.dict())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle

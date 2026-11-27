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


@router.get("/", response_model=List[PetrolPumpResponse])
def list_petrol_pumps(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return db.query(PetrolPump).filter(
        PetrolPump.is_active.is_(True)
    ).all()


@router.post(
    "/",
    response_model=PetrolPumpResponse,
    status_code=status.HTTP_201_CREATED
)
def create_petrol_pump(
    pump_in: PetrolPumpCreate,
    db: Session = Depends(get_db),
    owner=Depends(get_current_owner)
):
    cleaned_name = pump_in.name.strip()

    # Check duplicate name
    existing_name = db.query(PetrolPump).filter(
        func.lower(func.trim(PetrolPump.name))
        == func.lower(cleaned_name)
    ).first()

    if existing_name:
        raise HTTPException(
            status_code=400,
            detail="Petrol pump name is already registered."
        )

    # Check duplicate GPS coordinates
    existing_location = db.query(PetrolPump).filter(
        PetrolPump.latitude == pump_in.latitude,
        PetrolPump.longitude == pump_in.longitude
    ).first()

    if existing_location:
        raise HTTPException(
            status_code=400,
            detail="A petrol pump is already registered at these GPS coordinates."
        )

    pump_data = pump_in.model_dump()
    pump_data["name"] = cleaned_name

    pump = PetrolPump(**pump_data)
    db.add(pump)

    try:
        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Petrol pump registration conflicts with an existing record."
        )

    db.refresh(pump)

    return pump
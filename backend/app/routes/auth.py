"""
Authentication Routes
---------------------
Routes for user sign-in, self-registration, and profile inspection:
- POST /api/auth/signup: Fleet Owner self-registration
- POST /api/auth/create-operator: Owner-provisioned driver/operator accounts (Owner only)
- GET  /api/auth/operators: List fleet operators (Owner only)
- POST /api/auth/login: Authenticate user & get JWT
- GET  /api/auth/me: Current user profile
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.models.user import User
from app.schemas.user import OwnerSignup, OperatorCreate, Token, UserResponse
from app.routes.deps import get_current_user, get_current_owner

router = APIRouter()


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED, summary="Fleet Owner Signup")
def signup(owner_in: OwnerSignup, db: Session = Depends(get_db)):
    """
    Public self-registration endpoint for Fleet Owners.
    All self-registered users are assigned the 'owner' role to manage their fleet.
    """
    username = owner_in.username.strip()
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{username}' is already registered. Please choose another username or log in."
        )

    new_user = User(
        username=username,
        password_hash=get_password_hash(owner_in.password),
        role="owner",
        full_name=owner_in.full_name.strip() if owner_in.full_name else None,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token(subject=new_user.id, role=new_user.role)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": new_user.role,
        "username": new_user.username,
        "user_id": new_user.id,
    }


@router.post("/create-operator", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create Operator (Owner Only)")
def create_operator(
    operator_in: OperatorCreate,
    db: Session = Depends(get_db),
    current_owner: User = Depends(get_current_owner)
):
    """
    Provisions a new Operator / Driver account for the fleet.
    Restricted to authenticated Fleet Owners.
    """
    username = operator_in.username.strip()
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{username}' is already registered."
        )

    operator_user = User(
        username=username,
        password_hash=get_password_hash(operator_in.password),
        role="operator",
        full_name=operator_in.full_name.strip() if operator_in.full_name else None,
        is_active=True
    )
    db.add(operator_user)
    db.commit()
    db.refresh(operator_user)
    return operator_user


@router.get("/operators", response_model=List[UserResponse], summary="List Fleet Operators (Owner Only)")
def list_operators(
    db: Session = Depends(get_db),
    current_owner: User = Depends(get_current_owner)
):
    """
    Lists all active drivers and operators provisioned under the fleet.
    Restricted to authenticated Fleet Owners.
    """
    return db.query(User).filter(User.role == "operator", User.is_active == True).all()


@router.post("/login", response_model=Token, summary="User Login (OAuth2 Form)")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Standard OAuth2 password authentication endpoint.
    Takes username and password form fields.
    Natively supports Swagger UI 'Authorize' unlock modal and standard OAuth2 clients.
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is deactivated")

    access_token = create_access_token(subject=user.id, role=user.role)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "user_id": user.id,
    }


@router.get("/me", response_model=UserResponse, summary="Get Current User Profile")
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns profile information of the currently authenticated user.
    """
    return current_user

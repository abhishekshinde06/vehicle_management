"""
Authentication Routes
---------------------
Routes for user sign-in and profile inspection:
- POST /api/auth/login
- GET  /api/auth/me
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.schemas.user import UserLogin, Token, UserResponse
from app.routes.deps import get_current_user

router = APIRouter()


@router.post("/login", response_model=Token, summary="User Login")
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates an Operator or Owner using username and password.

    Returns:
        Token: Contains JWT access token and user role ('operator' or 'owner').
    """
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.password_hash):
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

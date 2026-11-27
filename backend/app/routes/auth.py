"""
Authentication Routes
---------------------
Routes for user authentication and account management:

  POST /api/auth/login            — Authenticate & get JWT (OAuth2 form, public)
  GET  /api/auth/me               — Current user profile (authenticated)
  POST /api/auth/create-operator  — Provision a new operator/driver (owner only)
  GET  /api/auth/operators        — List all active operators (owner only)

Design decisions (MVP / single-transporter):
- Public owner self-registration is DISABLED.
  The initial owner account is created exclusively via `seed.py`.
  This prevents unauthorized parties from registering as owners.
- Only an authenticated owner can create operator accounts.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, get_password_hash
from app.models.user import User
from app.schemas.user import OperatorCreate, Token, UserResponse
from app.routes.deps import get_current_user, get_current_owner

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /login — public, OAuth2 form
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=Token,
    summary="User Login",
    description=(
        "Standard OAuth2 password-flow endpoint. "
        "Accepts `username` and `password` as form fields and returns a signed JWT. "
        "Works natively with the Swagger UI **Authorize** button."
    ),
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Authenticates a user (owner **or** operator) and issues a signed JWT.

    - Uses OAuth2 password-flow form fields (`username`, `password`).
    - The returned `access_token` must be sent as `Authorization: Bearer <token>`
      on every subsequent request.
    - Token payload contains `sub` (user UUID) and `role` for RBAC enforcement.
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Contact the fleet owner.",
        )

    access_token = create_access_token(subject=user.id, role=user.role)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "user_id": user.id,
    }


# ---------------------------------------------------------------------------
# GET /me — authenticated
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current User Profile",
    description="Returns the profile of the currently authenticated user.",
)
def me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user's profile (id, username, role, full_name)."""
    return current_user


# ---------------------------------------------------------------------------
# POST /create-operator — owner only
# ---------------------------------------------------------------------------

@router.post(
    "/create-operator",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Operator Account (Owner Only)",
    description=(
        "Provisions a new driver / operator account for the fleet. "
        "**Requires an authenticated owner JWT.** "
        "Operators can log in and submit fuel entries but cannot access owner-only routes."
    ),
)
def create_operator(
    operator_in: OperatorCreate,
    db: Session = Depends(get_db),
    current_owner: User = Depends(get_current_owner),
):
    """
    Creates a new operator account under the authenticated owner.

    - `username` must be unique across the system.
    - The new account is assigned `role = "operator"` automatically.
    - Only an authenticated owner can call this endpoint (HTTP 403 otherwise).
    """
    username = operator_in.username.strip()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{username}' is already taken.",
        )

    operator = User(
        username=username,
        password_hash=get_password_hash(operator_in.password),
        role="operator",
        full_name=operator_in.full_name,
        is_active=True,
    )
    db.add(operator)
    db.commit()
    db.refresh(operator)
    return operator


# ---------------------------------------------------------------------------
# GET /operators — owner only
# ---------------------------------------------------------------------------

@router.get(
    "/operators",
    response_model=List[UserResponse],
    summary="List Fleet Operators (Owner Only)",
    description="Returns all active operator/driver accounts provisioned under this fleet.",
)
def list_operators(
    db: Session = Depends(get_db),
    current_owner: User = Depends(get_current_owner),
):
    """Lists every active operator. Restricted to authenticated owners."""
    return (
        db.query(User)
        .filter(User.role == "operator", User.is_active == True)  # noqa: E712
        .all()
    )

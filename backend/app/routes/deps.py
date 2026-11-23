"""
Authentication & Role-Based Access Control Dependencies
-------------------------------------------------------
Provides reusable dependencies for FastAPI routes:
- `get_current_user`: Decodes JWT token and retrieves the authenticated user.
- `require_role`: Restricts endpoints to specific user roles (e.g. operator, owner).
"""

from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

# OAuth2 scheme for Swagger UI documentation
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Validates the JWT bearer token passed in the Authorization header.

    Args:
        db (Session): Database session.
        token (str): JWT token string.

    Returns:
        User: Authenticated User model instance.

    Raises:
        HTTPException(401): If token is invalid, expired, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_role(allowed_roles: List[str]):
    """
    Role check dependency generator.

    Args:
        allowed_roles (List[str]): List of allowed role names (e.g. ['owner']).

    Returns:
        Callable: Dependency returning the user if their role is permitted.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {allowed_roles}. Your role: '{current_user.role}'"
            )
        return current_user
    return role_checker


# Convenient role guards
get_current_operator = require_role(["operator", "owner"])
get_current_owner = require_role(["owner"])

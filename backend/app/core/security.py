"""
Core Security Utilities
-----------------------
This module handles all cryptographic security operations:
1. One-way password hashing using the industry-standard `bcrypt` algorithm.
2. Secure verification of plain-text passwords against stored bcrypt hashes.
3. Generation of signed JSON Web Tokens (JWT) for stateless user authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any
import bcrypt
from jose import jwt,JWTError
from app.core.config import settings


def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password using bcrypt with a randomized salt.

    Args:
        password (str): The plain-text password provided by the user (e.g. during registration or seeding).

    Returns:
        str: A secure 60-character bcrypt hash string (e.g. '$2b$12$...').
             This hash is safe to store in the database.
    """
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a stored bcrypt hash.

    Args:
        plain_password (str): The plain-text password entered by the user during login.
        hashed_password (str): The previously stored bcrypt hash retrieved from the database.

    Returns:
        bool: True if the password matches the hash, False otherwise.
    """
    pwd_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)


def create_access_token(subject: Union[str, Any], role: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generates a cryptographically signed JSON Web Token (JWT).

    The token payload encodes:
    - 'sub': The unique User ID (subject of the token).
    - 'role': The user role ('operator' or 'owner') for quick client-side and server-side authorization checks.
    - 'exp': Expiration timestamp (after which the token is invalid).

    Args:
        subject (str | Any): Unique identifier of the user (e.g., user UUID).
        role (str): The role assigned to the user ('operator' or 'owner').
        expires_delta (Optional[timedelta]): Custom token lifetime. Defaults to settings.ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        str: Encoded JWT string to be sent in the HTTP Authorization header (Bearer <token>).
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
    "exp": expire,
    "sub": str(subject),
    "role": role,
    "purpose": "access"
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_gps_verification_token(
    user_id: str,
    pump_id: str
) -> str:

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "pump_id": str(pump_id),
        "purpose": "gps_verification",
        "iat": now,
        "exp": now + timedelta(minutes=15)
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
def validate_gps_verification_token(
    token: str,
    user_id: str,
    pump_id: str
) -> bool:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require_exp": True}
        )

        return (
            payload.get("purpose") == "gps_verification"
            and payload.get("sub") == str(user_id)
            and payload.get("pump_id") == str(pump_id)
        )

    except JWTError:
        return False
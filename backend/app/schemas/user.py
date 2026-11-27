"""
User Schemas
------------
Pydantic request / response models for authentication and user management.

NOTE: OwnerSignup has been intentionally removed.
      Owner accounts are created exclusively via seed.py (MVP policy).
      Only authenticated owners can provision operator accounts.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class OperatorCreate(BaseModel):
    """Body for POST /api/auth/create-operator (owner only)."""
    username: str = Field(
        ..., min_length=3, max_length=50,
        description="Unique username for the driver/operator",
        examples=["ramesh_driver"],
    )
    password: str = Field(
        ..., min_length=8,
        description="Password — minimum 8 characters, no spaces",
        examples=["secure123"],
    )
    full_name: str = Field(
        ..., min_length=1, max_length=100,
        description="Full name of the driver/operator (required)",
        examples=["Ramesh Kumar"],
    )

    @field_validator("username")
    @classmethod
    def validate_username_trimmed(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("Username must be at least 3 non-whitespace characters")
        if any(ch.isspace() for ch in stripped):
            raise ValueError("Username cannot contain spaces or whitespace")
        return stripped

    @field_validator("password")
    @classmethod
    def validate_password_no_whitespace(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Password cannot be empty or whitespace")
        if any(ch.isspace() for ch in value):
            raise ValueError("Password cannot contain spaces or whitespace")
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value

    @field_validator("full_name")
    @classmethod
    def validate_full_name_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Full name is required and cannot be blank")
        return stripped


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class Token(BaseModel):
    """Returned by POST /api/auth/login on success."""
    access_token: str = Field(..., description="Signed JWT — include as 'Authorization: Bearer <token>'")
    token_type: str = Field("bearer", description="Always 'bearer'")
    role: str = Field(..., description="User role: 'owner' or 'operator'")
    username: str = Field(..., description="Authenticated username")
    user_id: str = Field(..., description="UUID of the authenticated user")


class UserResponse(BaseModel):
    """Public representation of a user account (no password hash)."""
    id: str
    username: str
    role: str
    full_name: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

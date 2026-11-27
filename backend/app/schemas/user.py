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
        description="Password — minimum 8 characters",
        examples=["secure123"],
    )
    full_name: Optional[str] = Field(
        None, max_length=100,
        description="Full name of the driver/operator",
        examples=["Ramesh Kumar"],
    )

    @field_validator("username")
    @classmethod
    def validate_username_trimmed(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("Username must be at least 3 non-whitespace characters")
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

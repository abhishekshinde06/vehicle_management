from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class OwnerSignup(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username for Fleet Owner")
    password: str = Field(..., min_length=6, description="Password (at least 6 characters)")
    full_name: Optional[str] = Field(None, max_length=100, description="Full name of Fleet Owner")


class OperatorCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username for driver/operator")
    password: str = Field(..., min_length=6, description="Password (at least 6 characters)")
    full_name: Optional[str] = Field(None, max_length=100, description="Full name of driver/operator")


# Backward compatibility alias
UserCreate = OwnerSignup


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    user_id: str


class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    full_name: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

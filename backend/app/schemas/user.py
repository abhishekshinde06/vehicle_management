from typing import Optional
from pydantic import BaseModel, ConfigDict

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

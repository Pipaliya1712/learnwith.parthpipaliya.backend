from pydantic import BaseModel
from typing import Optional, List
from enum import Enum


class UserRole(str, Enum):
    admin = "admin"
    developer = "developer"


class UserOut(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    role: str
    is_blocked: bool
    email_verified: bool
    created_at: str
    updated_at: str


class UpdateRoleRequest(BaseModel):
    role: UserRole


class UsersListResponse(BaseModel):
    users: List[UserOut]
    total: int
    page: int


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "OK"

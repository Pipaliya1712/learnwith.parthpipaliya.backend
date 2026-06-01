from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional


# ─── Signup ─────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    confirm_password: str
    display_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("display_name")
    @classmethod
    def display_name_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Display name must be at least 2 characters")
        if len(v) > 50:
            raise ValueError("Display name must be at most 50 characters")
        return v


# ─── OTP ────────────────────────────────────────────────────────────────────

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

    @field_validator("otp")
    @classmethod
    def otp_length(cls, v: str) -> str:
        if len(v) != 6 or not v.isdigit():
            raise ValueError("OTP must be a 6-digit code")
        return v


class ResendOTPRequest(BaseModel):
    email: EmailStr


# ─── Login ──────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    stay_logged_in: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserProfile"


# ─── Password Reset ──────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v


# ─── Profile Update ──────────────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def display_name_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Display name must be at least 2 characters")
        if len(v) > 50:
            raise ValueError("Display name must be at most 50 characters")
        return v


class UpdateEmailRequest(BaseModel):
    email: EmailStr


class VerifyEmailUpdateRequest(BaseModel):
    otp: str

    @field_validator("otp")
    @classmethod
    def otp_length(cls, v: str) -> str:
        if len(v) != 6 or not v.isdigit():
            raise ValueError("OTP must be a 6-digit code")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


# ─── User Profile ────────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    role: str
    is_blocked: bool
    email_verified: bool
    created_at: str
    updated_at: str


# ─── Generic Response ────────────────────────────────────────────────────────

class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: str

from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import get_settings
from app.database import get_supabase
from app.models.auth import UserProfile

security = HTTPBearer()


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    expire_hours: Optional[int] = None,
) -> str:
    settings = get_settings()
    hours = expire_hours or settings.jwt_expire_hours
    expire = datetime.now(timezone.utc) + timedelta(hours=hours)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserProfile:
    payload = decode_token(credentials.credentials)
    user_id: str = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    supabase = get_supabase()
    result = (
        supabase.table("profiles")
        .select("id, email, display_name, avatar_url, role, is_blocked, email_verified, created_at, updated_at")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )

    result_data = getattr(result, 'data', None)
    if not result_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    profile = result_data
    if profile.get("is_blocked"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been blocked. Contact support.",
        )

    return UserProfile(**profile)


def is_super_admin(user: UserProfile, settings) -> bool:
    super_emails = [e.strip().lower() for e in (settings.super_admin_email or "").split(",") if e.strip()]
    return user.email.lower() in super_emails


async def require_admin(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
    settings = get_settings()
    if current_user.role != "admin" and not is_super_admin(current_user, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_super_admin(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
    settings = get_settings()
    if not is_super_admin(current_user, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user

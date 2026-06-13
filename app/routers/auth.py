from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File
import uuid
import os
from passlib.context import CryptContext
from app.models.auth import (
    SignupRequest, VerifyOTPRequest, ResendOTPRequest,
    LoginRequest, ForgotPasswordRequest, ResetPasswordRequest,
    UpdateProfileRequest, UpdateEmailRequest, VerifyEmailUpdateRequest,
    ChangePasswordRequest, UserProfile, SuccessResponse, LoginResponse,
)
from app.database import get_supabase
from app.config import get_settings
from app.dependencies import create_access_token, get_current_user
from app.services.email_service import send_otp_email
from app.services.otp_service import generate_otp, store_otp, verify_and_consume_otp
from app.services.captcha_service import generate_math_captcha, verify_captcha

router = APIRouter(prefix="/auth", tags=["Auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── CAPTCHA ─────────────────────────────────────────────────────────────────

@router.get("/captcha")
async def get_captcha():
    question, token = generate_math_captcha()
    return {"question": question, "captcha_token": token}


# ─── SIGNUP ──────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest):
    if not verify_captcha(body.captcha_token, body.captcha_answer):
        raise HTTPException(status_code=400, detail="Invalid CAPTCHA")
        
    settings = get_settings()
    supabase = get_supabase()
    username = body.display_name.strip()

    # Check if email exists
    existing = (
        supabase.table("profiles")
        .select("id, email_verified")
        .eq("email", body.email)
        .maybe_single()
        .execute()
    )

    # Check username uniqueness
    username_query = supabase.table("profiles").select("id").ilike("display_name", username)
    existing_data = getattr(existing, 'data', None)
    if existing_data:
        username_query = username_query.neq("id", existing_data["id"])
    username_result = username_query.maybe_single().execute()

    if getattr(username_result, 'data', None):
        raise HTTPException(status_code=400, detail="This username is already taken")

    password_hash = pwd_context.hash(body.password)

    if existing_data:
        if existing_data["email_verified"]:
            raise HTTPException(status_code=400, detail="This email is already registered")
        # Unverified user — update credentials and resend OTP
        supabase.table("profiles").update({
            "display_name": username,
            "password_hash": password_hash,
        }).eq("id", existing_data["id"]).execute()
    else:
        # New user
        role = "admin" if body.email == settings.super_admin_email else "developer"
        result = supabase.table("profiles").insert({
            "email": body.email,
            "display_name": username,
            "password_hash": password_hash,
            "email_verified": False,
            "role": role,
        }).execute()
        if not getattr(result, 'data', None):
            raise HTTPException(status_code=500, detail="Failed to create account")

    otp = generate_otp()
    store_otp(body.email, "signup", otp)

    try:
        send_otp_email(to=body.email, otp=otp, display_name=username)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to send verification email")

    return SuccessResponse(message="Verification email sent")


# ─── VERIFY OTP ──────────────────────────────────────────────────────────────

@router.post("/verify-otp", response_model=SuccessResponse)
async def verify_otp(body: VerifyOTPRequest):
    supabase = get_supabase()

    profile_result = (
        supabase.table("profiles")
        .select("id")
        .eq("email", body.email)
        .maybe_single()
        .execute()
    )
    if not getattr(profile_result, 'data', None):
        raise HTTPException(status_code=404, detail="No account found with this email")

    valid = verify_and_consume_otp(body.email, "signup", body.otp)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    supabase.table("profiles").update({"email_verified": True}).eq("email", body.email).execute()
    return SuccessResponse(message="Email verified successfully")


# ─── RESEND OTP ──────────────────────────────────────────────────────────────

@router.post("/resend-otp", response_model=SuccessResponse)
async def resend_otp(body: ResendOTPRequest):
    supabase = get_supabase()
    result = (
        supabase.table("profiles")
        .select("id, email_verified, display_name")
        .eq("email", body.email)
        .maybe_single()
        .execute()
    )
    result_data = getattr(result, 'data', None)
    if not result_data:
        raise HTTPException(status_code=404, detail="No account found with this email")
    if result_data["email_verified"]:
        raise HTTPException(status_code=400, detail="Email is already verified. You can log in.")

    otp = generate_otp()
    store_otp(body.email, "signup", otp)
    try:
        send_otp_email(to=body.email, otp=otp, display_name=result_data.get("display_name") or "User")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to send verification email")

    return SuccessResponse(message="Verification code resent")


# ─── LOGIN ───────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    if not verify_captcha(body.captcha_token, body.captcha_answer):
        raise HTTPException(status_code=400, detail="Invalid CAPTCHA")
        
    settings = get_settings()
    supabase = get_supabase()

    result = (
        supabase.table("profiles")
        .select("id, role, is_blocked, email_verified, password_hash, email, display_name, avatar_url, created_at, updated_at")
        .eq("email", body.email)
        .maybe_single()
        .execute()
    )

    result_data = getattr(result, 'data', None)
    if not result_data:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    profile = result_data

    if not profile["email_verified"]:
        raise HTTPException(status_code=403, detail="Please verify your email before logging in")

    if profile["is_blocked"]:
        raise HTTPException(status_code=403, detail="Your account has been blocked. Contact support.")

    if not pwd_context.verify(body.password, profile["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    from app.dependencies import promote_role_if_super_admin
    promote_role_if_super_admin(profile, settings)

    expire_hours = 24 if body.stay_logged_in else 1
    token = create_access_token(
        user_id=profile["id"],
        email=profile["email"],
        role=profile["role"],
        expire_hours=expire_hours,
    )

    user_profile = UserProfile(
        id=profile["id"],
        email=profile["email"],
        display_name=profile.get("display_name"),
        avatar_url=profile.get("avatar_url"),
        role=profile["role"],
        is_blocked=profile["is_blocked"],
        email_verified=profile["email_verified"],
        created_at=profile["created_at"],
        updated_at=profile["updated_at"],
    )

    return LoginResponse(access_token=token, user=user_profile)


# ─── FORGOT PASSWORD ─────────────────────────────────────────────────────────

@router.post("/forgot-password", response_model=SuccessResponse)
async def forgot_password(body: ForgotPasswordRequest):
    supabase = get_supabase()
    result = (
        supabase.table("profiles")
        .select("id")
        .eq("email", body.email)
        .maybe_single()
        .execute()
    )
    # Do NOT reveal whether the email exists
    if not getattr(result, 'data', None):
        return SuccessResponse(message="If this email is registered, you will receive a reset code")

    otp = generate_otp()
    store_otp(body.email, "reset", otp)
    try:
        send_otp_email(to=body.email, otp=otp, display_name="User")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to send reset email")

    return SuccessResponse(message="Password reset code sent")


# ─── RESET PASSWORD ──────────────────────────────────────────────────────────

@router.post("/reset-password", response_model=SuccessResponse)
async def reset_password(body: ResetPasswordRequest):
    supabase = get_supabase()

    result = (
        supabase.table("profiles")
        .select("id")
        .eq("email", body.email)
        .maybe_single()
        .execute()
    )
    result_data = getattr(result, 'data', None)
    if not result_data:
        raise HTTPException(status_code=404, detail="No account found with this email")

    valid = verify_and_consume_otp(body.email, "reset", body.otp)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    password_hash = pwd_context.hash(body.password)
    supabase.table("profiles").update({"password_hash": password_hash}).eq("id", result_data["id"]).execute()

    return SuccessResponse(message="Password reset successfully")


# ─── GET ME ──────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserProfile)
async def get_me(current_user: UserProfile = Depends(get_current_user)):
    return current_user

@router.get("/me/progress")
async def get_my_progress(current_user: UserProfile = Depends(get_current_user)):
    from app.services.progress_service import get_user_progress
    supabase = get_supabase()
    progress = get_user_progress(supabase, current_user.id)
    if not progress:
        # Return default zeros if no progress exists yet
        return {
            "user_id": current_user.id,
            "points": 0,
            "level": "V1",
            "solved_challenges": 0,
            "approved_submissions": 0,
            "rejected_submissions": 0,
            "updated_at": "now()"
        }
    return progress



# ─── UPDATE PROFILE ──────────────────────────────────────────────────────────

@router.patch("/profile", response_model=SuccessResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: UserProfile = Depends(get_current_user),
):
    supabase = get_supabase()
    username = body.display_name.strip()

    existing = (
        supabase.table("profiles")
        .select("id")
        .ilike("display_name", username)
        .neq("id", current_user.id)
        .maybe_single()
        .execute()
    )
    if getattr(existing, 'data', None):
        raise HTTPException(status_code=400, detail="This username is already taken")

    supabase.table("profiles").update({"display_name": username}).eq("id", current_user.id).execute()
    return SuccessResponse(message="Profile updated")


# ─── UPLOAD AVATAR ───────────────────────────────────────────────────────────

@router.post("/avatar", response_model=SuccessResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: UserProfile = Depends(get_current_user),
):
    supabase = get_supabase()
    settings = get_settings()
    bucket_name = settings.supabase_bucket
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
        
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"{current_user.id}/{uuid.uuid4()}{file_ext}"
    
    # Upload to supabase bucket 'avatars'
    try:
        # Delete all existing avatars for this user
        try:
            files = supabase.storage.from_(bucket_name).list(current_user.id)
            if files:
                files_to_remove = [f"{current_user.id}/{f['name']}" for f in files if f['name']]
                if files_to_remove:
                    supabase.storage.from_(bucket_name).remove(files_to_remove)
        except Exception:
            pass # Ignore errors in deletion of old avatars
                
        contents = await file.read()
        res = supabase.storage.from_(bucket_name).upload(file_name, contents, {"content-type": file.content_type})
        
        # Get public url
        public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
        
        # Update user profile
        supabase.table("profiles").update({"avatar_url": public_url}).eq("id", current_user.id).execute()
        
        return SuccessResponse(message="Avatar updated successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")


# ─── UPDATE EMAIL (step 1: send OTP to new email) ────────────────────────────

@router.patch("/email", response_model=SuccessResponse)
async def request_email_update(
    body: UpdateEmailRequest,
    current_user: UserProfile = Depends(get_current_user),
):
    otp = generate_otp()
    store_otp(str(body.email), "email_update", otp)
    try:
        send_otp_email(to=str(body.email), otp=otp, display_name=current_user.display_name or "User")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to send verification email")

    return SuccessResponse(message="Verification code sent to new email")


# ─── VERIFY EMAIL UPDATE (step 2: commit the change) ────────────────────────

class EmailVerifyBody(UpdateEmailRequest):
    """Used to verify email update: contains the new email and OTP."""
    otp: str

@router.post("/email/verify", response_model=SuccessResponse)
async def verify_email_update(
    body: EmailVerifyBody,
    current_user: UserProfile = Depends(get_current_user),
):
    supabase = get_supabase()
    new_email = str(body.email)

    valid = verify_and_consume_otp(new_email, "email_update", body.otp)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    supabase.table("profiles").update({
        "email": new_email,
        "email_verified": True,
    }).eq("id", current_user.id).execute()

    return SuccessResponse(message="Email updated successfully")


# ─── CHANGE PASSWORD ─────────────────────────────────────────────────────────

@router.patch("/password", response_model=SuccessResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: UserProfile = Depends(get_current_user),
):
    supabase = get_supabase()

    profile_result = (
        supabase.table("profiles")
        .select("password_hash")
        .eq("id", current_user.id)
        .maybe_single()
        .execute()
    )

    profile_data = getattr(profile_result, 'data', None)
    if not profile_data or not pwd_context.verify(
        body.current_password, profile_data["password_hash"]
    ):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_hash = pwd_context.hash(body.new_password)
    supabase.table("profiles").update({"password_hash": new_hash}).eq("id", current_user.id).execute()

    return SuccessResponse(message="Password changed successfully")

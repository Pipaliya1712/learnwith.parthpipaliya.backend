import random
import string
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
from app.database import get_supabase

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

OTP_EXPIRE_MINUTES = 10


def generate_otp(length: int = 6) -> str:
    """Generate a cryptographically random numeric OTP."""
    return "".join(random.choices(string.digits, k=length))


def hash_otp(otp: str) -> str:
    """Bcrypt-hash an OTP before storing in DB."""
    return pwd_context.hash(otp)


def verify_otp_hash(plain_otp: str, hashed: str) -> bool:
    """Verify a plain OTP against its stored bcrypt hash."""
    return pwd_context.verify(plain_otp, hashed)


def store_otp(email: str, purpose: str, otp: str) -> None:
    """
    Upsert (overwrite) the OTP for this email+purpose.
    Old OTP is automatically invalidated because of UNIQUE(email, purpose).
    The OTP is stored hashed — never plaintext.
    """
    supabase = get_supabase()
    expires_at = (
        datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)
    ).isoformat()

    hashed = hash_otp(otp)

    # Delete any existing OTP for this email+purpose first (upsert equivalent)
    supabase.table("otp_tokens").delete().eq("email", email).eq(
        "purpose", purpose
    ).execute()

    supabase.table("otp_tokens").insert(
        {
            "email": email,
            "purpose": purpose,
            "hashed_otp": hashed,
            "expires_at": expires_at,
        }
    ).execute()


def verify_and_consume_otp(email: str, purpose: str, plain_otp: str) -> bool:
    """
    Verify the OTP. If valid, immediately delete it from the DB (consume it).
    Returns True if valid, False otherwise.
    """
    supabase = get_supabase()

    result = (
        supabase.table("otp_tokens")
        .select("id, hashed_otp, expires_at")
        .eq("email", email)
        .eq("purpose", purpose)
        .maybe_single()
        .execute()
    )

    result_data = getattr(result, 'data', None)
    if not result_data:
        return False

    row = result_data

    # Check expiry
    expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        # Expired — clean up
        supabase.table("otp_tokens").delete().eq("id", row["id"]).execute()
        return False

    # Verify hash
    if not verify_otp_hash(plain_otp, row["hashed_otp"]):
        return False

    # Consume — delete immediately after successful verification
    supabase.table("otp_tokens").delete().eq("id", row["id"]).execute()
    return True

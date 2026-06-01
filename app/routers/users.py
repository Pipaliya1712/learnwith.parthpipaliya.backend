from fastapi import APIRouter, HTTPException, Depends
from app.models.user import UpdateRoleRequest, SuccessResponse, UsersListResponse, UserOut
from app.database import get_supabase
from app.dependencies import require_admin, require_super_admin
from app.models.auth import UserProfile

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UsersListResponse)
async def list_users(current_user: UserProfile = Depends(require_admin)):
    supabase = get_supabase()
    result = supabase.table("profiles").select("id, email, display_name, role, is_blocked, email_verified, created_at, updated_at").order("created_at", desc=True).execute()
    users = [UserOut(**u) for u in (result.data or [])]
    return UsersListResponse(users=users, total=len(users))


@router.patch("/{user_id}/block", response_model=SuccessResponse)
async def block_user(
    user_id: str,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    supabase.table("profiles").update({"is_blocked": True}).eq("id", user_id).execute()
    return SuccessResponse(message="User blocked")


@router.patch("/{user_id}/unblock", response_model=SuccessResponse)
async def unblock_user(
    user_id: str,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    supabase.table("profiles").update({"is_blocked": False}).eq("id", user_id).execute()
    return SuccessResponse(message="User unblocked")


@router.patch("/{user_id}/role", response_model=SuccessResponse)
async def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    current_user: UserProfile = Depends(require_super_admin),
):
    supabase = get_supabase()
    supabase.table("profiles").update({"role": body.role.value}).eq("id", user_id).execute()
    return SuccessResponse(message=f"User role updated to {body.role.value}")

# ─── GET USER PROFILE ────────────────────────────────────────────────────────

@router.get("/{user_id}/profile")
async def get_user_profile(user_id: str):
    supabase = get_supabase()
    
    user_res = supabase.table("profiles").select("id, email, display_name, avatar_url, role, created_at").eq("id", user_id).maybe_single().execute()
    user_data = getattr(user_res, 'data', None)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
        
    projects_res = supabase.table("projects").select("id, name, slug, summary, is_visible, is_deleted, created_at, updated_at").eq("created_by", user_id).order("created_at", desc=True).execute()
    projects_data = getattr(projects_res, 'data', [])
    
    comments_res = supabase.table("comments").select("id, content, created_at, updated_at, projects(name, slug)").eq("user_id", user_id).is_("deleted_at", None).order("created_at", desc=True).execute()
    comments_data = getattr(comments_res, 'data', [])
    
    return {
        "user": user_data,
        "projects": projects_data,
        "comments": comments_data
    }

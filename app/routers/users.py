from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from app.models.user import UpdateRoleRequest, SuccessResponse, UsersListResponse, UserOut, PublicUserOut, PublicUsersSearchResponse
from app.database import get_supabase
from app.dependencies import require_admin, require_super_admin
from app.models.auth import UserProfile

router = APIRouter(prefix="/users", tags=["Users"])


# ─── LEADERBOARD ─────────────────────────────────────────────────────────────

@router.get("/leaderboard")
async def get_leaderboard_endpoint(limit: int = Query(50, ge=1, le=100)):
    from app.services.progress_service import get_leaderboard
    supabase = get_supabase()
    data = get_leaderboard(supabase, limit)
    
    # Map the response
    leaderboard = []
    for index, user in enumerate(data):
        profile = user.pop("profiles", {}) or {}
        leaderboard.append({
            "rank": index + 1,
            "user_id": user["user_id"],
            "display_name": profile.get("display_name") or "Anonymous Learner",
            "avatar_url": profile.get("avatar_url"),
            "points": user["points"],
            "level": user["level"],
            "solved_challenges": user["solved_challenges"]
        })
        
    return {"items": leaderboard}

# ─── PUBLIC USER SEARCH ──────────────────────────────────────────────────────

@router.get("/search", response_model=PublicUsersSearchResponse)
async def search_users(
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(12, ge=1, le=100),
):
    supabase = get_supabase()
    query = supabase.table("profiles").select(
        "id, display_name, avatar_url, role, created_at",
        count="exact"
    ).eq("is_blocked", False)

    if search:
        query = query.ilike("display_name", f"%{search}%")

    result = query.order("display_name", desc=False).range(skip, skip + limit - 1).execute()
    users = [PublicUserOut(**u) for u in (result.data or [])]
    return PublicUsersSearchResponse(
        users=users,
        total=getattr(result, 'count', 0) or 0
    )


@router.get("/platform-metrics")
async def get_platform_metrics():
    supabase = get_supabase()
    challenges_res = supabase.table("challenges").select("id", count="exact").limit(1).execute()
    users_res = supabase.table("profiles").select("id", count="exact").limit(1).execute()
    submissions_res = supabase.table("submissions").select("id", count="exact").limit(1).execute()
    
    return {
        "total_challenges": getattr(challenges_res, 'count', 0) or 0,
        "total_users": getattr(users_res, 'count', 0) or 0,
        "total_submissions": getattr(submissions_res, 'count', 0) or 0
    }

@router.get("", response_model=UsersListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_desc: bool = Query(True),
    user: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    query = supabase.table("profiles").select(
        "id, email, display_name, role, is_blocked, email_verified, created_at, updated_at",
        count="exact"
    )

    if user:
        query = query.or_(f"email.ilike.%{user}%,display_name.ilike.%{user}%")
    if role in {"admin", "developer"}:
        query = query.eq("role", role)
    if status == "blocked":
        query = query.eq("is_blocked", True)
    elif status == "active":
        query = query.eq("is_blocked", False)

    allowed_sort_columns = {"email", "display_name", "role", "created_at", "is_blocked"}
    sort_col = sort_by if sort_by in allowed_sort_columns else "created_at"
    result = query.order(sort_col, desc=sort_desc).range(skip, skip + limit - 1).execute()
    users = [UserOut(**u) for u in (result.data or [])]
    return UsersListResponse(
        users=users,
        total=getattr(result, 'count', 0) or 0,
        page=(skip // limit) + 1 if limit > 0 else 1
    )


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

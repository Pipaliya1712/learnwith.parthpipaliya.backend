from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from app.models.comment import AddCommentRequest, UpdateCommentRequest, SuccessResponse
from app.database import get_supabase
from app.dependencies import get_current_user, require_admin, require_super_admin
from app.models.auth import UserProfile

router = APIRouter(prefix="/comments", tags=["Comments"])

# ─── GET ALL COMMENTS (ADMIN) ────────────────────────────────────────────────

@router.get("/admin")
async def get_all_comments(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_desc: bool = Query(True),
    content: Optional[str] = None,
    user_email: Optional[str] = None,
    project_name: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: UserProfile = Depends(require_admin)
):
    supabase = get_supabase()
    
    query = supabase.table("comments").select("*, projects!inner(name), profiles!comments_user_id_fkey!inner(email, display_name, is_blocked)", count="exact")
    
    if content:
        query = query.ilike("content", f"%{content}%")
    if user_email:
        query = query.or_(f"email.ilike.%{user_email}%,display_name.ilike.%{user_email}%", foreign_table="profiles!comments_user_id_fkey")
    if project_name:
        query = query.ilike("projects.name", f"%{project_name}%")
    
    if status_filter == "blocked":
        query = query.eq("profiles.is_blocked", True)
    elif status_filter == "active":
        query = query.eq("profiles.is_blocked", False)
        
    sort_col = sort_by
    if sort_col == "project_name":
        sort_col = "projects.name"
    elif sort_col == "user_email":
        sort_col = "profiles.email"
        
    query = query.order(sort_col, desc=sort_desc)
    query = query.range(skip, skip + limit - 1)
    
    result = query.execute()
    
    return {
        "data": getattr(result, 'data', []),
        "total": getattr(result, 'count', 0),
        "page": (skip // limit) + 1 if limit > 0 else 1
    }

# ─── ADD COMMENT ─────────────────────────────────────────────────────────────
@router.post("", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    body: AddCommentRequest,
    current_user: UserProfile = Depends(get_current_user),
):
    content = body.content.strip()
    if not content or len(content) > 2000:
        raise HTTPException(status_code=400, detail="Comment must be between 1 and 2000 characters")

    supabase = get_supabase()
    result = supabase.table("comments").insert({
        "project_id": body.project_id,
        "user_id": current_user.id,
        "content": content,
    }).execute()

    if not getattr(result, 'data', None):
        raise HTTPException(status_code=500, detail="Failed to post comment")

    return SuccessResponse(message="Comment posted")

# ─── UPDATE OWN COMMENT ──────────────────────────────────────────────────────
# GET PROJECT COMMENTS
@router.get("/project/{project_id}")
async def get_project_comments(
    project_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(5, ge=1, le=100),
):
    supabase = get_supabase()
    comments = supabase.table("comments").select(
        "id, project_id, content, created_at, updated_at, deleted_at, deleted_by, user_id, profiles!comments_user_id_fkey!inner(display_name, email, avatar_url, is_blocked)",
        count="exact"
    ).eq("project_id", project_id).is_("deleted_at", None).eq("profiles.is_blocked", False).order("created_at", desc=True).range(skip, skip + limit - 1).execute()

    return {
        "comments": getattr(comments, 'data', []),
        "total": getattr(comments, 'count', 0) or 0,
        "page": (skip // limit) + 1 if limit > 0 else 1
    }


@router.patch("/{comment_id}/own", response_model=SuccessResponse)
async def update_own_comment(
    comment_id: str,
    body: UpdateCommentRequest,
    current_user: UserProfile = Depends(get_current_user),
):
    content = body.content.strip()
    if not content or len(content) > 2000:
        raise HTTPException(status_code=400, detail="Comment must be between 1 and 2000 characters")

    supabase = get_supabase()
    result = supabase.table("comments").select("id, user_id, deleted_at").eq("id", comment_id).maybe_single().execute()
    result_data = getattr(result, 'data', None)

    if not result_data or result_data["user_id"] != current_user.id:
        raise HTTPException(status_code=404, detail="Comment not found")
        
    if result_data.get("deleted_at"):
        raise HTTPException(status_code=400, detail="Cannot edit a deleted comment")

    supabase.table("comments").update({
        "content": content,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", comment_id).execute()

    return SuccessResponse(message="Comment updated")


# ─── HARD DELETE COMMENT (SUPER ADMIN) ───────────────────────────────────────
@router.delete("/{comment_id}", response_model=SuccessResponse)
async def super_admin_delete_comment(
    comment_id: str,
    current_user: UserProfile = Depends(require_super_admin),
):
    supabase = get_supabase()
    supabase.table("comments").delete().eq("id", comment_id).execute()
    return SuccessResponse(message="Comment permanently deleted")

# ─── SOFT DELETE COMMENT (SUPER ADMIN) ───────────────────────────────────────
@router.delete("/{comment_id}/soft", response_model=SuccessResponse)
async def admin_soft_delete_comment(
    comment_id: str,
    current_user: UserProfile = Depends(require_super_admin),
):
    supabase = get_supabase()
    supabase.table("comments").update({
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "deleted_by": current_user.id
    }).eq("id", comment_id).is_("deleted_at", None).execute()
    return SuccessResponse(message="Comment soft deleted")

# ─── SOFT DELETE OWN COMMENT ─────────────────────────────────────────────────
@router.delete("/{comment_id}/own", response_model=SuccessResponse)
async def delete_own_comment(
    comment_id: str,
    current_user: UserProfile = Depends(get_current_user),
):
    supabase = get_supabase()
    result = supabase.table("comments").select("id, user_id").eq("id", comment_id).maybe_single().execute()
    result_data = getattr(result, 'data', None)

    if not result_data or result_data["user_id"] != current_user.id:
        raise HTTPException(status_code=404, detail="Comment not found")

    supabase.table("comments").update({
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "deleted_by": current_user.id
    }).eq("id", comment_id).is_("deleted_at", None).execute()

    return SuccessResponse(message="Comment deleted")

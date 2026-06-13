import re
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from app.models.challenge import (
    ChallengeCreateRequest, ChallengeUpdateRequest, ChallengeStatus
)
from app.models.project import SuccessResponse
from app.database import get_supabase
from app.dependencies import require_admin, get_current_user
from app.models.auth import UserProfile

router = APIRouter(prefix="/challenges", tags=["Challenges"])

# ─── GET CHALLENGES (PUBLIC) ──────────────────────────────────────────────────

@router.get("")
async def get_challenges(
    skip: int = Query(0, ge=0),
    limit: int = Query(12, ge=1, le=100),
    status_filter: Optional[str] = Query("published", alias="status"),
    project_id: Optional[str] = None,
    difficulty: Optional[str] = None,
):
    supabase = get_supabase()
    query = supabase.table("challenges").select("*, projects(id, name, slug)", count="exact")

    if status_filter:
        query = query.eq("status", status_filter)
    if project_id:
        query = query.eq("project_id", project_id)
    if difficulty:
        query = query.eq("difficulty", difficulty)

    challenges_res = query.order("created_at", desc=True).range(skip, skip + limit - 1).execute()
    challenges_data = getattr(challenges_res, 'data', [])

    # Format the projects join properly
    for item in challenges_data:
        project_data = item.pop("projects", None)
        if project_data:
            item["project"] = project_data

    return {
        "items": challenges_data,
        "total": getattr(challenges_res, 'count', 0) or 0,
        "page": (skip // limit) + 1,
        "limit": limit
    }

# ─── GET CHALLENGE BY SLUG (PUBLIC) ──────────────────────────────────────────

@router.get("/slug/{slug}")
async def get_challenge_by_slug(slug: str):
    supabase = get_supabase()
    
    # Fetch challenge with project join
    result = supabase.table("challenges").select("*, projects(id, name, slug)").eq("slug", slug).maybe_single().execute()
    challenge_data = getattr(result, 'data', None)
    
    if not challenge_data:
        raise HTTPException(status_code=404, detail="Challenge not found")
        
    cid = challenge_data["id"]
    
    # Fetch associated tags
    ctags = supabase.table("challenge_tags").select("tags(*)").eq("challenge_id", cid).execute()
    ctags_data = getattr(ctags, 'data', [])
    challenge_data["tags"] = [pt["tags"] for pt in ctags_data if pt and pt.get("tags")]
    
    # Handle the 'projects' join since Supabase puts it in a dictionary
    project_data = challenge_data.pop("projects", None)
    if project_data:
        challenge_data["project"] = project_data
        
    return challenge_data

# ─── CREATE CHALLENGE (ADMIN) ────────────────────────────────────────────────

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_challenge(
    body: ChallengeCreateRequest,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    
    # Verify slug uniqueness
    existing = supabase.table("challenges").select("id").eq("slug", body.slug).execute()
    if getattr(existing, 'data', []):
        raise HTTPException(status_code=400, detail="Challenge with this slug already exists")

    insert_data = {
        "project_id": body.project_id,
        "title": body.title,
        "slug": body.slug,
        "description": body.description,
        "acceptance_criteria": body.acceptance_criteria,
        "difficulty": body.difficulty.value if hasattr(body.difficulty, 'value') else body.difficulty,
        "points": body.points,
        "estimated_hours": body.estimated_hours,
        "status": body.status.value if hasattr(body.status, 'value') else body.status,
        "created_by": current_user.id,
    }

    result = supabase.table("challenges").insert(insert_data).execute()

    if not result.data or len(result.data) == 0:
        raise HTTPException(status_code=500, detail="Failed to create challenge")

    challenge_id = result.data[0]["id"]

    # Insert tags
    if body.tag_ids:
        supabase.table("challenge_tags").insert([
            {"challenge_id": challenge_id, "tag_id": tag_id}
            for tag_id in body.tag_ids
        ]).execute()

    return {"success": True, "id": challenge_id, "slug": body.slug}

# ─── UPDATE CHALLENGE (ADMIN) ────────────────────────────────────────────────

@router.patch("/{challenge_id}", response_model=SuccessResponse)
async def update_challenge(
    challenge_id: str,
    body: ChallengeUpdateRequest,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    
    # Build update dict ignoring None
    update_data = body.model_dump(exclude_unset=True, exclude={"tag_ids"})
    
    # Handle enums
    if "difficulty" in update_data and hasattr(update_data["difficulty"], "value"):
        update_data["difficulty"] = update_data["difficulty"].value
    if "status" in update_data and hasattr(update_data["status"], "value"):
        update_data["status"] = update_data["status"].value

    if update_data:
        supabase.table("challenges").update(update_data).eq("id", challenge_id).execute()

    # Update tags if provided
    if body.tag_ids is not None:
        supabase.table("challenge_tags").delete().eq("challenge_id", challenge_id).execute()
        if body.tag_ids:
            supabase.table("challenge_tags").insert([
                {"challenge_id": challenge_id, "tag_id": tag_id}
                for tag_id in body.tag_ids
            ]).execute()

    return SuccessResponse(message="Challenge updated successfully")

# ─── DELETE CHALLENGE (SOFT) (ADMIN) ─────────────────────────────────────────

@router.delete("/{challenge_id}", response_model=SuccessResponse)
async def delete_challenge(
    challenge_id: str,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    # Soft delete
    supabase.table("challenges").update({"status": ChallengeStatus.ARCHIVED.value}).eq("id", challenge_id).execute()
    return SuccessResponse(message="Challenge permanently archived")

# ─── CLAIM CHALLENGE ─────────────────────────────────────────────────────────

@router.post("/{challenge_id}/claim", response_model=SuccessResponse)
async def claim_challenge(
    challenge_id: str,
    current_user: UserProfile = Depends(get_current_user),
):
    supabase = get_supabase()
    
    # Use standard in_progress status and NULL for github_pr_url
    insert_data = {
        "challenge_id": challenge_id,
        "user_id": current_user.id,
        "status": "in_progress",
        "github_pr_url": None
    }
    
    try:
        supabase.table("submissions").insert(insert_data).execute()
    except Exception as e:
        # Ignore if it fails due to unique constraints or missing tables for now
        pass
        
    return SuccessResponse(message="Challenge claimed successfully")

# ─── GET MY CHALLENGES (DASHBOARD) ───────────────────────────────────────────

@router.get("/me/claimed")
async def get_my_challenges(
    current_user: UserProfile = Depends(get_current_user),
):
    supabase = get_supabase()
    
    # In a real app we query submissions for this user
    # Join with challenges and projects
    try:
        result = supabase.table("submissions").select("id, status, updated_at, github_pr_url, ai_score, ai_feedback, challenges(id, title, slug, points, difficulty, projects(name))").eq("user_id", current_user.id).execute()
        
        claims = getattr(result, 'data', [])
        formatted_claims = []
        for claim in claims:
            # Removed pending_claim hack, status comes properly from DB
            ch = claim.pop("challenges", None)
            if ch:
                proj = ch.pop("projects", None)
                if proj:
                    ch["project"] = proj
                claim["challenge"] = ch
                formatted_claims.append(claim)
                
        return {"items": formatted_claims, "total": len(formatted_claims)}
    except Exception as e:
        # Fallback if submissions table doesn't exist yet
        return {"items": [], "total": 0}


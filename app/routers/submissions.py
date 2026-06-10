from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status, Query
from app.models.submission import (
    SubmissionCreateRequest, SubmissionReviewRequest, SubmissionStatus, SubmissionResponse
)
from app.models.project import SuccessResponse
from app.database import get_supabase
from app.dependencies import require_admin
from app.models.auth import UserProfile
# from app.dependencies import get_current_user # To be used when actual auth is wired

router = APIRouter(prefix="/submissions", tags=["Submissions"])

# ─── CREATE OR UPDATE SUBMISSION ─────────────────────────────────────────────

@router.post("", response_model=SuccessResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    body: SubmissionCreateRequest,
    current_user: UserProfile = Depends(require_admin), # Allow admin for testing, change to get_current_user in production
):
    from app.dependencies import get_current_user
    supabase = get_supabase()
    
    # Check if the user already has a submission (or a draft) for this challenge
    existing = supabase.table("submissions").select("id, status").eq("challenge_id", body.challenge_id).eq("user_id", current_user.id).execute()
    
    if existing.data:
        # If it's already approved, they shouldn't submit again
        if existing.data[0]["status"] == SubmissionStatus.APPROVED.value:
            raise HTTPException(status_code=400, detail="Challenge already approved")
            
        # Update the existing draft or rejected submission
        update_data = {
            "github_pr_url": str(body.github_pr_url),
            "github_repo_url": str(body.github_repo_url) if body.github_repo_url else None,
            "status": SubmissionStatus.SUBMITTED.value,
            "updated_at": "now()"
            # Note: body.notes is intentionally excluded to prevent DB errors
        }
        supabase.table("submissions").update(update_data).eq("id", existing.data[0]["id"]).execute()
        return SuccessResponse(message="Submission updated successfully")
        
    # Create new submission
    insert_data = {
        "challenge_id": body.challenge_id,
        "user_id": current_user.id,
        "github_pr_url": str(body.github_pr_url),
        "github_repo_url": str(body.github_repo_url) if body.github_repo_url else None,
        "status": SubmissionStatus.SUBMITTED.value
        # Note: body.notes is intentionally excluded to prevent DB errors
    }
    
    result = supabase.table("submissions").insert(insert_data).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create submission")
        
    return SuccessResponse(message="Submission created successfully")

# ─── GET CURRENT USER'S SUBMISSIONS ──────────────────────────────────────────

@router.get("/me")
async def get_my_submissions(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserProfile = Depends(require_admin), # Normally get_current_user
):
    from app.dependencies import get_current_user
    supabase = get_supabase()
    
    # Query with challenge details
    result = supabase.table("submissions").select("*, challenges(id, title, slug, points, difficulty, projects(name))", count="exact").eq("user_id", current_user.id).order("updated_at", desc=True).range(skip, skip + limit - 1).execute()
    
    submissions_data = getattr(result, 'data', [])
    for sub in submissions_data:
        ch = sub.pop("challenges", None)
        if ch:
            proj = ch.pop("projects", None)
            if proj:
                ch["project"] = proj
            sub["challenge"] = ch
            
    return {
        "items": submissions_data,
        "total": getattr(result, 'count', 0) or 0,
        "page": (skip // limit) + 1,
        "limit": limit
    }

# ─── GET PENDING REVIEWS (ADMIN QUEUE) ───────────────────────────────────────

@router.get("/pending")
async def get_pending_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    
    # Query submissions that are submitted or under_review
    result = supabase.table("submissions").select("*, profiles(username, avatar_url), challenges(title, points)", count="exact").in_("status", [SubmissionStatus.SUBMITTED.value, SubmissionStatus.UNDER_REVIEW.value]).order("created_at", desc=False).range(skip, skip + limit - 1).execute()
    
    return {
        "items": getattr(result, 'data', []),
        "total": getattr(result, 'count', 0) or 0,
        "page": (skip // limit) + 1,
        "limit": limit
    }

# ─── GET SINGLE SUBMISSION ───────────────────────────────────────────────────

@router.get("/{submission_id}")
async def get_submission(
    submission_id: str,
    current_user: UserProfile = Depends(require_admin), # In prod: verify user owns it or is admin
):
    supabase = get_supabase()
    result = supabase.table("submissions").select("*, profiles(username, avatar_url), challenges(title, description, points, projects(name))").eq("id", submission_id).maybe_single().execute()
    
    if not getattr(result, 'data', None):
        raise HTTPException(status_code=404, detail="Submission not found")
        
    return result.data

# ─── UPDATE SUBMISSION STATUS (ADMIN/AI) ─────────────────────────────────────

@router.patch("/{submission_id}/review", response_model=SuccessResponse)
async def review_submission(
    submission_id: str,
    body: SubmissionReviewRequest,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    
    # Ensure it exists
    existing = supabase.table("submissions").select("id, status, user_id, challenge_id, challenges(points)").eq("id", submission_id).maybe_single().execute()
    if not getattr(existing, 'data', None):
        raise HTTPException(status_code=404, detail="Submission not found")
        
    update_data = {
        "status": body.status.value,
        "updated_at": "now()"
    }
    
    if body.ai_score is not None:
        update_data["ai_score"] = body.ai_score
    if body.ai_feedback is not None:
        update_data["ai_feedback"] = body.ai_feedback
        
    supabase.table("submissions").update(update_data).eq("id", submission_id).execute()
    
    # Award points if status is changing to approved (and wasn't already approved to prevent double-counting)
    from app.services.progress_service import increment_user_progress
    if body.status == SubmissionStatus.APPROVED and existing.data["status"] != SubmissionStatus.APPROVED.value:
        points_to_add = existing.data["challenges"]["points"] if existing.data.get("challenges") else 0
        increment_user_progress(supabase, existing.data["user_id"], points_to_add)
        
    return SuccessResponse(message=f"Submission updated to {body.status.value}")

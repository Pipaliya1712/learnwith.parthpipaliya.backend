from enum import Enum
from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class SubmissionStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"

class SubmissionBase(BaseModel):
    challenge_id: str
    github_pr_url: HttpUrl
    github_repo_url: Optional[HttpUrl] = None
    notes: Optional[str] = None

class SubmissionCreateRequest(SubmissionBase):
    pass

class SubmissionReviewRequest(BaseModel):
    status: SubmissionStatus
    ai_score: Optional[int] = None
    ai_feedback: Optional[str] = None
    # Potential fields for manual admin grading in the future
    # manual_feedback: Optional[str] = None
    # points_awarded: Optional[int] = None

class SubmissionResponse(SubmissionBase):
    id: str
    user_id: str
    status: SubmissionStatus
    ai_score: Optional[int] = None
    ai_feedback: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

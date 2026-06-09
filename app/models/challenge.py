from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from .project import TagOut


class ChallengeDifficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class ChallengeStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ChallengeCreateRequest(BaseModel):
    project_id: str
    title: str
    slug: str
    description: str
    acceptance_criteria: Optional[str] = None
    difficulty: ChallengeDifficulty
    points: int = 0
    estimated_hours: Optional[int] = None
    status: ChallengeStatus = ChallengeStatus.DRAFT
    tag_ids: List[str] = []


class ChallengeUpdateRequest(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    difficulty: Optional[ChallengeDifficulty] = None
    points: Optional[int] = None
    estimated_hours: Optional[int] = None
    status: Optional[ChallengeStatus] = None
    tag_ids: Optional[List[str]] = None


class ProjectBrief(BaseModel):
    id: str
    name: str
    slug: str


class ChallengeOut(BaseModel):
    id: str
    project_id: str
    title: str
    slug: str
    description: str
    acceptance_criteria: Optional[str] = None
    difficulty: ChallengeDifficulty
    points: int
    estimated_hours: Optional[int] = None
    status: ChallengeStatus
    created_by: Optional[str] = None
    created_at: str
    updated_at: str
    
    # Joined relations
    project: Optional[ProjectBrief] = None
    tags: List[TagOut] = []


class ChallengeListOut(BaseModel):
    items: List[ChallengeOut]
    page: int
    limit: int
    total: int

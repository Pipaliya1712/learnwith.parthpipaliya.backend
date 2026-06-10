from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserProgressResponse(BaseModel):
    user_id: str
    points: int
    level: str
    solved_challenges: int
    approved_submissions: int
    rejected_submissions: int
    updated_at: datetime

class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    display_name: str
    avatar_url: Optional[str] = None
    points: int
    level: str
    solved_challenges: int

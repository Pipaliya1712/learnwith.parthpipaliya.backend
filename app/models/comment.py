from pydantic import BaseModel
from typing import Optional


class AddCommentRequest(BaseModel):
    project_id: str
    content: str

    def validate_content(self) -> bool:
        return 1 <= len(self.content.strip()) <= 2000

class UpdateCommentRequest(BaseModel):
    content: str

    def validate_content(self) -> bool:
        return 1 <= len(self.content.strip()) <= 2000


class CommentOut(BaseModel):
    id: str
    project_id: str
    user_id: str
    content: str
    created_at: str
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None
    user_display_name: Optional[str] = None


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "OK"

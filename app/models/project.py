from pydantic import BaseModel
from typing import Optional, List


class FeatureItem(BaseModel):
    title: str
    description: str


class ImprovementItem(BaseModel):
    title: str
    description: Optional[str] = None


class BugItem(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "low"  # low | medium | high | critical


class ProjectImage(BaseModel):
    id: str
    image_url: str
    alt_text: Optional[str] = None
    display_order: int


class TagOut(BaseModel):
    id: str
    name: str
    slug: str


class ProjectCreateRequest(BaseModel):
    name: str
    summary: str
    live_link: Optional[str] = ""
    repo_link: str
    additional_info: Optional[str] = None
    is_visible: bool = False


class ProjectUpdateRequest(BaseModel):
    name: str
    summary: str
    live_link: Optional[str] = ""
    repo_link: str
    additional_info: Optional[str] = None
    is_visible: bool = False
    features: List[FeatureItem] = []
    improvements: List[ImprovementItem] = []
    bugs: List[BugItem] = []
    tag_ids: List[str] = []


class ProjectOut(BaseModel):
    id: str
    name: str
    slug: str
    summary: str
    live_link: Optional[str] = None
    repo_link: Optional[str] = None
    additional_info: Optional[str] = None
    is_visible: bool
    is_deleted: bool
    landing_page_order: Optional[int] = None
    created_by: Optional[str] = None
    created_at: str
    updated_at: str
    features: List[FeatureItem] = []
    improvements: List[ImprovementItem] = []
    bugs: List[BugItem] = []
    tags: List[TagOut] = []
    images: List[ProjectImage] = []


class ToggleVisibilityRequest(BaseModel):
    visible: bool


class ReorderRequest(BaseModel):
    ordered_ids: List[str]


class TagCreateRequest(BaseModel):
    name: str


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "OK"

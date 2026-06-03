import re
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status
from app.models.project import (
    ProjectCreateRequest, ProjectUpdateRequest, ProjectOut,
    ToggleVisibilityRequest, ReorderRequest, TagCreateRequest,
    TagOut, SuccessResponse,
)
from app.database import get_supabase
from app.dependencies import get_current_user, require_admin
from app.models.auth import UserProfile

router = APIRouter(prefix="/projects", tags=["Projects"])


def generate_slug(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")

def ensure_unique_slug(supabase, base_slug: str, exclude_project_id: str = None) -> str:
    slug = base_slug
    counter = 1
    while True:
        query = supabase.table("projects").select("id").eq("slug", slug)
        if exclude_project_id:
            query = query.neq("id", exclude_project_id)
        result = query.execute()
        
        if not getattr(result, 'data', []):
            break
        
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


# ─── GET LANDING PROJECTS ────────────────────────────────────────────────────

@router.get("/landing")
async def get_landing_projects():
    supabase = get_supabase()
    projects = supabase.table("projects").select("*").eq("is_visible", True).eq("is_deleted", False).order("landing_page_order").order("created_at", desc=True).limit(10).execute()
    
    if not getattr(projects, 'data', None):
        return {"projects": [], "tags": []}
        
    project_ids = [p["id"] for p in projects.data]
    tags_res = supabase.table("tags").select("id, name, slug").order("name").execute()
    tags = getattr(tags_res, 'data', [])
    
    all_images = supabase.table("project_images").select("*").in_("project_id", project_ids).order("display_order").execute() if project_ids else None
    images_data = getattr(all_images, 'data', []) if all_images else []
    
    all_project_tags = supabase.table("project_tags").select("project_id, tags(id, name, slug)").in_("project_id", project_ids).execute() if project_ids else None
    project_tags_data = getattr(all_project_tags, 'data', []) if all_project_tags else []
    
    for p in projects.data:
        p["images"] = [img for img in images_data if img["project_id"] == p["id"]]
        p["tags"] = [pt["tags"] for pt in project_tags_data if pt["project_id"] == p["id"] and pt.get("tags")]
        
    return {"projects": projects.data, "tags": tags}

# ─── GET DASHBOARD PROJECTS ──────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard_projects():
    supabase = get_supabase()
    projects = supabase.table("projects").select("*").eq("is_deleted", False).order("created_at", desc=True).execute()
    projects_data = getattr(projects, 'data', [])
    
    if not projects_data:
        return {"projects": []}
        
    project_ids = [p["id"] for p in projects_data]
    all_project_tags = supabase.table("project_tags").select("project_id, tags(id, name, slug)").in_("project_id", project_ids).execute()
    project_tags_data = getattr(all_project_tags, 'data', [])
    
    all_images = supabase.table("project_images").select("*").in_("project_id", project_ids).order("display_order").execute()
    images_data = getattr(all_images, 'data', [])
    
    for p in projects_data:
        p["tags"] = [pt["tags"] for pt in project_tags_data if pt["project_id"] == p["id"] and pt.get("tags")]
        p["images"] = [img for img in images_data if img["project_id"] == p["id"]]
        
    return {"projects": projects_data}

# ─── GET ADMIN PROJECTS ──────────────────────────────────────────────────────

@router.get("/admin")
async def get_admin_projects(current_user: UserProfile = Depends(require_admin)):
    supabase = get_supabase()
    projects = supabase.table("projects").select("*").order("created_at", desc=True).execute()
    projects_data = getattr(projects, 'data', [])
    
    if not projects_data:
        return {"projects": []}
        
    project_ids = [p["id"] for p in projects_data]
    all_project_tags = supabase.table("project_tags").select("project_id, tags(id, name, slug)").in_("project_id", project_ids).execute()
    project_tags_data = getattr(all_project_tags, 'data', [])
    
    for p in projects_data:
        p["tags"] = [pt["tags"] for pt in project_tags_data if pt["project_id"] == p["id"] and pt.get("tags")]
        
    return {"projects": projects_data}

# ─── GET PROJECT DETAILS ─────────────────────────────────────────────────────

@router.get("/slug/{slug}")
async def get_project_by_slug(slug: str):
    supabase = get_supabase()
    result = supabase.table("projects").select("*").eq("slug", slug).eq("is_deleted", False).maybe_single().execute()
    project_data = getattr(result, 'data', None)
    
    if not project_data:
        raise HTTPException(status_code=404, detail="Project not found")
        
    pid = project_data["id"]
    
    images = supabase.table("project_images").select("*").eq("project_id", pid).order("display_order").execute()
    project_data["images"] = getattr(images, 'data', [])
    
    features = supabase.table("features").select("*").eq("project_id", pid).order("display_order").execute()
    project_data["features"] = getattr(features, 'data', [])
    
    improvements = supabase.table("improvements").select("*").eq("project_id", pid).order("display_order").execute()
    project_data["improvements"] = getattr(improvements, 'data', [])
    
    bugs = supabase.table("bugs").select("*").eq("project_id", pid).order("display_order").execute()
    project_data["bugs"] = getattr(bugs, 'data', [])
    
    ptags = supabase.table("project_tags").select("tags(*)").eq("project_id", pid).execute()
    ptags_data = getattr(ptags, 'data', [])
    project_data["tags"] = [pt["tags"] for pt in ptags_data if pt.get("tags")]
    
    comments = supabase.table("comments").select("id, content, created_at, updated_at, user_id, profiles!comments_user_id_fkey(display_name, email, avatar_url, is_blocked)").eq("project_id", pid).is_("deleted_at", None).order("created_at", desc=True).execute()
    project_data["comments"] = getattr(comments, 'data', [])
    
    creator = supabase.table("profiles").select("display_name").eq("id", project_data["created_by"]).maybe_single().execute()
    creator_data = getattr(creator, 'data', None)
    project_data["creator_name"] = creator_data["display_name"] if creator_data else "Unknown"
    
    # Get related projects based on tags
    tag_ids = [t["id"] for t in project_data["tags"]]
    related_projects = []
    if tag_ids:
        related_pts = supabase.table("project_tags").select("project_id").in_("tag_id", tag_ids).execute()
        related_pts_data = getattr(related_pts, 'data', [])
        r_pids = list(set([pt["project_id"] for pt in related_pts_data if pt["project_id"] != pid]))
        if r_pids:
            related_res = supabase.table("projects").select("*").in_("id", r_pids).eq("is_deleted", False).limit(4).execute()
            related_projects = getattr(related_res, 'data', [])
            if related_projects:
                r_fetched_ids = [r["id"] for r in related_projects]
                r_imgs_res = supabase.table("project_images").select("*").in_("project_id", r_fetched_ids).order("display_order").execute()
                r_imgs = getattr(r_imgs_res, 'data', [])
                
                r_tags_res = supabase.table("project_tags").select("project_id, tags(id, name, slug)").in_("project_id", r_fetched_ids).execute()
                r_tags = getattr(r_tags_res, 'data', [])
                
                for r in related_projects:
                    r["images"] = [i for i in r_imgs if i["project_id"] == r["id"]]
                    r["tags"] = [pt["tags"] for pt in r_tags if pt["project_id"] == r["id"] and pt.get("tags")]
                    
    project_data["related_projects"] = related_projects
    
    return project_data

# ─── GET PROJECT BY ID (ADMIN) ───────────────────────────────────────────────

@router.get("/id/{id}")
async def get_project_by_id(id: str, current_user: UserProfile = Depends(require_admin)):
    supabase = get_supabase()
    result = supabase.table("projects").select("*").eq("id", id).maybe_single().execute()
    project_data = getattr(result, 'data', None)
    
    if not project_data:
        raise HTTPException(status_code=404, detail="Project not found")
        
    pid = project_data["id"]
    
    images = supabase.table("project_images").select("*").eq("project_id", pid).order("display_order").execute()
    project_data["images"] = getattr(images, 'data', [])
    
    features = supabase.table("features").select("*").eq("project_id", pid).order("display_order").execute()
    project_data["features"] = getattr(features, 'data', [])
    
    improvements = supabase.table("improvements").select("*").eq("project_id", pid).order("display_order").execute()
    project_data["improvements"] = getattr(improvements, 'data', [])
    
    bugs = supabase.table("bugs").select("*").eq("project_id", pid).order("display_order").execute()
    project_data["bugs"] = getattr(bugs, 'data', [])
    
    ptags = supabase.table("project_tags").select("tag_id").eq("project_id", pid).execute()
    project_data["selectedTagIds"] = [pt["tag_id"] for pt in getattr(ptags, 'data', [])]
    
    return project_data

# ─── CREATE PROJECT ──────────────────────────────────────────────────────────

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    base_slug = generate_slug(body.name)
    slug = ensure_unique_slug(supabase, base_slug)

    result = supabase.table("projects").insert({
        "name": body.name,
        "summary": body.summary,
        "live_link": body.live_link or "",
        "repo_link": body.repo_link,
        "additional_info": body.additional_info,
        "is_visible": body.is_visible,
        "slug": slug,
        "created_by": current_user.id,
    }).execute()

    if not result.data or len(result.data) == 0:
        raise HTTPException(status_code=500, detail="Failed to create project")

    project_id = result.data[0]["id"]

    # Insert features
    if body.features:
        supabase.table("features").insert([
            {"project_id": project_id, "title": f.title, "description": f.description, "display_order": i}
            for i, f in enumerate(body.features)
        ]).execute()

    # Insert improvements
    if body.improvements:
        supabase.table("improvements").insert([
            {"project_id": project_id, "title": imp.title, "description": imp.description, "display_order": i}
            for i, imp in enumerate(body.improvements)
        ]).execute()

    # Insert bugs
    if body.bugs:
        supabase.table("bugs").insert([
            {"project_id": project_id, "title": b.title, "description": b.description, "severity": b.severity, "display_order": i}
            for i, b in enumerate(body.bugs)
        ]).execute()

    # Insert tags
    if body.tag_ids:
        supabase.table("project_tags").insert([
            {"project_id": project_id, "tag_id": tag_id}
            for tag_id in body.tag_ids
        ]).execute()

    return {"success": True, "id": project_id, "slug": slug}


# ─── UPDATE PROJECT ──────────────────────────────────────────────────────────

@router.patch("/{project_id}", response_model=SuccessResponse)
async def update_project(
    project_id: str,
    body: ProjectUpdateRequest,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    base_slug = generate_slug(body.name)
    slug = ensure_unique_slug(supabase, base_slug, exclude_project_id=project_id)

    supabase.table("projects").update({
        "name": body.name,
        "summary": body.summary,
        "live_link": body.live_link or "",
        "repo_link": body.repo_link,
        "additional_info": body.additional_info,
        "is_visible": body.is_visible,
        "slug": slug,
    }).eq("id", project_id).execute()

    # Update features
    supabase.table("features").delete().eq("project_id", project_id).execute()
    if body.features:
        supabase.table("features").insert([
            {"project_id": project_id, "title": f.title, "description": f.description, "display_order": i}
            for i, f in enumerate(body.features)
        ]).execute()

    # Update improvements
    supabase.table("improvements").delete().eq("project_id", project_id).execute()
    if body.improvements:
        supabase.table("improvements").insert([
            {"project_id": project_id, "title": imp.title, "description": imp.description, "display_order": i}
            for i, imp in enumerate(body.improvements)
        ]).execute()

    # Update bugs
    supabase.table("bugs").delete().eq("project_id", project_id).execute()
    if body.bugs:
        supabase.table("bugs").insert([
            {"project_id": project_id, "title": b.title, "description": b.description, "severity": b.severity, "display_order": i}
            for i, b in enumerate(body.bugs)
        ]).execute()

    # Update tags
    supabase.table("project_tags").delete().eq("project_id", project_id).execute()
    if body.tag_ids:
        supabase.table("project_tags").insert([
            {"project_id": project_id, "tag_id": tag_id}
            for tag_id in body.tag_ids
        ]).execute()

    return SuccessResponse(message="Project updated")


# ─── DELETE PROJECT (HARD DELETE) ──────────────────────────────────────────────

@router.delete("/{project_id}", response_model=SuccessResponse)
async def delete_project(
    project_id: str,
    current_user: UserProfile = Depends(require_admin),
):
    from app.config import get_settings
    supabase = get_supabase()
    settings = get_settings()
    bucket_name = settings.supabase_bucket_projects

    # 1. Delete all images from Supabase Storage
    # We list the folder containing the project images
    try:
        files = supabase.storage.from_(bucket_name).list(project_id)
        if files:
            files_to_remove = [f"{project_id}/{f['name']}" for f in files if f['name']]
            if files_to_remove:
                supabase.storage.from_(bucket_name).remove(files_to_remove)
    except Exception:
        pass # Ignore storage deletion errors if folder doesn't exist

    # 2. Delete the project from the database.
    # Assuming ON DELETE CASCADE is properly set for relations (comments, features, bugs, improvements, project_tags, project_images).
    # If not, Supabase might throw a foreign key error, but the user confirmed cascading is set up.
    supabase.table("projects").delete().eq("id", project_id).execute()
    
    return SuccessResponse(message="Project and all associated data permanently deleted")


# ─── TOGGLE VISIBILITY ────────────────────────────────────────────────────────

@router.patch("/{project_id}/visibility", response_model=SuccessResponse)
async def toggle_visibility(
    project_id: str,
    body: ToggleVisibilityRequest,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()

    if body.visible:
        count_result = supabase.table("projects").select("id", count="exact").eq("is_visible", True).eq("is_deleted", False).execute()
        if (count_result.count or 0) >= 10:
            raise HTTPException(status_code=400, detail="Maximum 10 projects can be visible on the landing page")

    supabase.table("projects").update({"is_visible": body.visible}).eq("id", project_id).execute()
    return SuccessResponse(message="Visibility updated")


# ─── REORDER LANDING PROJECTS ────────────────────────────────────────────────

@router.post("/reorder", response_model=SuccessResponse)
async def reorder_projects(
    body: ReorderRequest,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    for i, pid in enumerate(body.ordered_ids):
        supabase.table("projects").update({"landing_page_order": i + 1}).eq("id", pid).execute()
    return SuccessResponse(message="Order updated")


# ─── UPLOAD IMAGE ────────────────────────────────────────────────────────────

@router.post("/{project_id}/images", response_model=SuccessResponse)
async def upload_image(
    project_id: str,
    file: UploadFile = File(...),
    current_user: UserProfile = Depends(require_admin),
):
    import uuid
    from app.config import get_settings
    supabase = get_supabase()
    
    # Check current image count limit (Max 5)
    count_res = supabase.table("project_images").select("id", count="exact").eq("project_id", project_id).execute()
    if (count_res.count or 0) >= 5:
        raise HTTPException(status_code=400, detail="Maximum limit of 5 images per project reached.")

    settings = get_settings()
    bucket_name = settings.supabase_bucket_projects
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    file_path = f"{project_id}/{uuid.uuid4()}.{ext}"
    content = await file.read()

    upload_result = supabase.storage.from_(bucket_name).upload(file_path, content)
    if upload_result.path is None:
        raise HTTPException(status_code=500, detail="Failed to upload image")

    public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)

    images = supabase.table("project_images").select("display_order").eq("project_id", project_id).order("display_order", desc=True).limit(1).execute()
    next_order = (images.data[0]["display_order"] + 1) if images.data else 0

    supabase.table("project_images").insert({
        "project_id": project_id,
        "image_url": public_url,
        "alt_text": file.filename,
        "display_order": next_order,
    }).execute()

    return SuccessResponse(message="Image uploaded")


# ─── DELETE IMAGE ─────────────────────────────────────────────────────────────

@router.delete("/images/{image_id}", response_model=SuccessResponse)
async def delete_image(
    image_id: str,
    current_user: UserProfile = Depends(require_admin),
):
    from app.config import get_settings
    supabase = get_supabase()
    settings = get_settings()
    bucket_name = settings.supabase_bucket_projects

    # Get image details to delete from bucket
    img_res = supabase.table("project_images").select("image_url, project_id").eq("id", image_id).maybe_single().execute()
    
    if img_res.data:
        image_url = img_res.data.get("image_url")
        project_id = img_res.data.get("project_id")
        if image_url and project_id:
            try:
                # Extract filename from URL (e.g. project_id/uuid.jpg)
                url_parts = image_url.split(f"/{bucket_name}/")
                if len(url_parts) == 2:
                    file_path = url_parts[1]
                    supabase.storage.from_(bucket_name).remove([file_path])
            except Exception:
                pass # Ignore storage removal errors

    # Delete database record
    supabase.table("project_images").delete().eq("id", image_id).execute()
    return SuccessResponse(message="Image deleted")


# ─── CREATE TAG ──────────────────────────────────────────────────────────────

@router.post("/tags", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create_tag(
    body: TagCreateRequest,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    slug = generate_slug(body.name)
    result = supabase.table("tags").insert({"name": body.name.strip(), "slug": slug}).execute()
    if not result.data or len(result.data) == 0:
        raise HTTPException(status_code=500, detail="Failed to create tag")
    return TagOut(**result.data[0])

# ─── GET ALL TAGS ────────────────────────────────────────────────────────────

@router.get("/tags")
async def get_tags():
    supabase = get_supabase()
    result = supabase.table("tags").select("*").order("name").execute()
    return getattr(result, 'data', [])

# ─── DELETE TAG ──────────────────────────────────────────────────────────────

@router.delete("/tags/{tag_id}", response_model=SuccessResponse)
async def delete_tag(
    tag_id: str,
    current_user: UserProfile = Depends(require_admin),
):
    supabase = get_supabase()
    
    # Check if tag exists
    existing = supabase.table("tags").select("id").eq("id", tag_id).maybe_single().execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Tag not found")
        
    # Delete the tag (cascade will handle project_tags)
    result = supabase.table("tags").delete().eq("id", tag_id).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to delete tag")
        
    return SuccessResponse(message="Tag deleted successfully")

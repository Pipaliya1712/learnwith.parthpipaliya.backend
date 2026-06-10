from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import auth, projects, comments, users, challenges, submissions

settings = get_settings()

app = FastAPI(
    title="Learn With API",
    description="Backend API for the Learn With platform — project showcase for open-source contributors.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS ────────────────────────────────────────────────────────────────────
# Only Next.js (Vercel) can call this API. The Next.js server-to-server
# requests don't go through the browser, so CORS is mainly for the docs UI.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── ROUTERS ─────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(comments.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(challenges.router, prefix="/api")
app.include_router(submissions.router, prefix="/api")


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "Learn With API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}

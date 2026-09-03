import logging
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.api.endpoints import vqa_router, caption_router, grounding_router, change_router, optical_sar_router, agent_router, land_cover_router
from backend.api.endpoints.auth import router as auth_router
from backend.api.auth import current_user
from backend.api.endpoints.jobs import router as jobs_router

# Configure Logger
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("satquery.api")

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="Backend API services for SatQuery AI - Interactive Remote Sensing Vision-Language Assistant."
)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
protected = [Depends(current_user)]
app.include_router(vqa_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(caption_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(grounding_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(change_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(optical_sar_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(land_cover_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(agent_router, prefix="/api/v1", tags=["Agent"], dependencies=protected)
app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
app.include_router(jobs_router, prefix="/api/v1", tags=["Jobs"])

@app.get("/")
async def root():
    return {
        "app": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "healthy",
        "debug_mode": settings.DEBUG
    }

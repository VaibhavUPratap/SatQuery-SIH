import logging
from pathlib import Path
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.config import settings
from backend.api.endpoints import vqa_router, caption_router, grounding_router, change_router, optical_sar_router, agent_router, land_cover_router
from backend.api.endpoints.auth import router as auth_router
from backend.api.auth import current_user
from backend.api.endpoints.jobs import router as jobs_router
from backend.api.endpoints.nisar import router as nisar_router

# Configure Logger
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("terrapulse.api")

app = FastAPI(
    title="TerraPulse AI API",
    version=settings.API_VERSION,
    description="Agentic Intelligence for NISAR-Based Earth Surface Change Detection — NASA Space Apps Challenge 2026."
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
app.include_router(nisar_router, prefix="/api/v1", tags=["NISAR Earth Observation"])
app.include_router(vqa_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(caption_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(grounding_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(change_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(optical_sar_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(land_cover_router, prefix="/api/v1", tags=["Specialist Tools"], dependencies=protected)
app.include_router(agent_router, prefix="/api/v1", tags=["Agent"], dependencies=protected)
app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
app.include_router(jobs_router, prefix="/api/v1", tags=["Jobs"])

nisar_assets = Path(__file__).resolve().parents[2] / "datasets" / "processed" / "bengaluru"
if nisar_assets.is_dir():
    app.mount("/api/v1/nisar/assets", StaticFiles(directory=nisar_assets), name="nisar-assets")

@app.get("/")
async def root():
    return {
        "app": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "healthy",
        "debug_mode": settings.DEBUG
    }

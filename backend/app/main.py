from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import init_db, SessionLocal
from app.api import auth, properties, meters, bills, tariffs, export_analytics, notifications, features
from app.services.seed import seed_service_types
from app.services.files import ensure_upload_dir, UPLOAD_ROOT

# frontend/dist is copied here for single-service deploy
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_upload_dir()
    db = SessionLocal()
    try:
        count = seed_service_types(db)
        db.commit()
        if count:
            print(f"Seeded {count} service types")
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(properties.router, prefix=settings.API_V1_PREFIX)
app.include_router(meters.router, prefix=settings.API_V1_PREFIX)
app.include_router(bills.router, prefix=settings.API_V1_PREFIX)
app.include_router(tariffs.router, prefix=settings.API_V1_PREFIX)
app.include_router(export_analytics.router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications.router, prefix=settings.API_V1_PREFIX)
app.include_router(features.router, prefix=settings.API_V1_PREFIX)

ensure_upload_dir()
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_ROOT)), name="uploads")


@app.get("/health")
def health():
    return {"status": "healthy", "version": settings.VERSION}


@app.get("/api")
def api_info():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "ok",
        "docs": "/docs",
    }


# Serve React build if present (production / Render)
if STATIC_DIR.is_dir() and (STATIC_DIR / "index.html").is_file():
    assets = STATIC_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith(("api/", "uploads/", "docs", "openapi", "redoc", "health")):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
else:

    @app.get("/")
    def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "ok",
            "hint": "Соберите frontend в backend/static для web-интерфейса",
        }

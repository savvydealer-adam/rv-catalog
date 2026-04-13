"""RV Catalog API -- Central knowledge base for all RV dealer websites."""

import os
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.auth import get_current_user, GOOGLE_CLIENT_ID
from backend.database import init_db
from backend.routers import manufacturers, models, health

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
PORT = int(os.getenv("PORT", "8080"))

app = FastAPI(
    title="RV Catalog API",
    description="Central RV manufacturer, model, and floorplan knowledge base",
    docs_url="/api-docs" if ENVIRONMENT == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes (protected by auth in production)
app.include_router(manufacturers.router, dependencies=[Depends(get_current_user)])
app.include_router(models.router, dependencies=[Depends(get_current_user)])
app.include_router(health.router, dependencies=[Depends(get_current_user)])


@app.get("/api/auth/config")
def auth_config():
    """Return OAuth config for the frontend (public, no auth required)."""
    return {
        "client_id": GOOGLE_CLIENT_ID,
        "environment": ENVIRONMENT,
    }


@app.get("/api/auth/me")
def auth_me(user: dict = Depends(get_current_user)):
    """Return the current authenticated user."""
    return user


@app.on_event("startup")
def startup():
    init_db()


# Serve dashboard static files (built React app)
DIST_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=PORT, reload=ENVIRONMENT == "development")

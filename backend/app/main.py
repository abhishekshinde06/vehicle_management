"""
FastAPI Main Application Entry Point
------------------------------------
Configures CORS, initializes database routes, and exposes authenticated APIs:
- /api/auth
- /api/vehicles
- /api/petrol-pumps
- /api/fuel-entries
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base  # noqa: F401 — imported so models register
from app.routes import auth, vehicles, petrol_pumps, fuel_entries

# NOTE: Table creation is managed by Alembic migrations.
# Run `alembic upgrade head` before starting the server.

# Create FastAPI instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Clean, role-based Vehicle Fuel & Mileage Tracking System API",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for mobile, tablet, and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Clean API Routers under settings.API_PREFIX (default: "/api")
app.include_router(auth.router, prefix=f"{settings.API_PREFIX}/auth", tags=["1. Authentication"])
app.include_router(vehicles.router, prefix=f"{settings.API_PREFIX}/vehicles", tags=["2. Fleet Vehicles"])
app.include_router(petrol_pumps.router, prefix=f"{settings.API_PREFIX}/petrol-pumps", tags=["3. Authorized Petrol Pumps"])
app.include_router(fuel_entries.router, prefix=f"{settings.API_PREFIX}/fuel-entries", tags=["4. Fuel Entries & Mileage"])


@app.get("/", summary="Health Check")
def health_check():
    """
    Root endpoint indicating API service health status and API documentation URL.
    """
    return {
        "status": "online",
        "service": settings.PROJECT_NAME,
        "docs": "/docs",
    }

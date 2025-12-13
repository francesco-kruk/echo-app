import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.db import get_settings, verify_connection, close_client
from app.routers import decks_router, cards_router, seed_router, learn_router
from app.auth import get_auth_settings

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    auth_settings = get_auth_settings()

    # Log authentication configuration
    if auth_settings.enabled:
        if auth_settings.is_configured():
            print(f"✓ Entra ID authentication enabled")
            print(f"  Tenant: {auth_settings.tenant_id}")
            print(f"  API Audience: {auth_settings.api_audience}")
        else:
            print("⚠ Authentication enabled but not configured (missing AZURE_TENANT_ID or AZURE_API_SCOPE)")
    else:
        print("⚠ Authentication DISABLED - using X-User-Id header fallback (dev mode)")

    if settings.is_configured():
        if verify_connection():
            print("✓ Connected to Cosmos DB")
        else:
            print("✗ Failed to connect to Cosmos DB - check configuration")
    else:
        print("⚠ Cosmos DB not configured (COSMOS_ENDPOINT/COSMOS_KEY not set)")

    yield

    # Shutdown
    close_client()
    print("✓ Cosmos DB connection closed")


app = FastAPI(
    title="Echo App API",
    description="A flashcard API backend for Azure Container Apps",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(decks_router)
app.include_router(cards_router)
app.include_router(seed_router)
app.include_router(learn_router)


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Echo App API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/healthz",
            "decks": "/decks",
            "cards": "/decks/{deck_id}/cards",
            "seed": "/seed",
        },
    }


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {"status": "healthy"}

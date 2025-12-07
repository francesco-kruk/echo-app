import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Echo API",
    description="A minimal FastAPI backend for Azure Container Apps",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class EchoRequest(BaseModel):
    message: str


class EchoResponse(BaseModel):
    echo: str


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Echo API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/healthz",
            "echo": "/echo",
        },
    }


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/echo", response_model=EchoResponse)
async def echo(request: EchoRequest):
    """Echo endpoint that mirrors the payload."""
    return EchoResponse(echo=request.message)

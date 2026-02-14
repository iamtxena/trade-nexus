"""FastAPI application entry point."""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.api.lona_routes import router as lona_router
from src.api.routes import router
from src.platform_api.errors import (
    PlatformAPIError,
    platform_api_error_handler,
    unhandled_error_handler,
)
from src.platform_api.router_v1 import router as platform_api_v1_router
from src.config import get_settings

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configure LangSmith tracing
settings = get_settings()
if settings.langsmith_tracing:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

app = FastAPI(
    title="Trade Nexus ML Backend",
    description="ML backend for autonomous trading orchestrator",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://*.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def platform_api_unhandled_error_middleware(request: Request, call_next):
    """Apply fallback v1 error envelope only to Platform API routes."""
    try:
        return await call_next(request)
    except Exception as exc:
        if request.url.path.startswith("/v1/"):
            logger.exception("Unhandled exception for Platform API request %s", request.url.path)
            return await unhandled_error_handler(request, exc)
        raise


# Include routes
app.include_router(router, prefix="/api")
app.include_router(lona_router, prefix="/api")
app.include_router(platform_api_v1_router)

# Register platform API error envelope handlers.
app.add_exception_handler(PlatformAPIError, platform_api_error_handler)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Trade Nexus ML Backend", "status": "running"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

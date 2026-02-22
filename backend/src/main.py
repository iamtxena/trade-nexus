"""FastAPI application entry point."""

import logging
import os
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.platform_api.auth_identity import resolve_validation_identity
from src.platform_api.errors import (
    PlatformAPIError,
    platform_api_error_handler,
    unhandled_error_handler,
)
from src.platform_api.observability import log_request_event, request_log_fields
from src.platform_api.router_v1 import router as platform_api_v1_router
from src.platform_api.router_v2 import router as platform_api_v2_router
from src.config import get_settings

logger = logging.getLogger(__name__)

_legacy_router_import_error: ModuleNotFoundError | None = None
try:
    from src.api.lona_routes import router as lona_router
    from src.api.routes import router as legacy_router
except ModuleNotFoundError as exc:
    optional_legacy_deps = {
        "langchain",
        "langchain_core",
        "langchain_xai",
        "numpy",
        "pandas",
        "scikit-learn",
        "sklearn",
        "torch",
    }
    if exc.name not in optional_legacy_deps:
        raise
    # Legacy /api routes depend on optional ML stack packages that are not required
    # for Platform API contract and runtime checks.
    lona_router = None
    legacy_router = None
    _legacy_router_import_error = exc

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


def _is_platform_request(path: str) -> bool:
    return path.startswith("/v1/") or path.startswith("/v2/")


def _is_v2_validation_request(path: str) -> bool:
    return path.startswith("/v2/validation")


def _is_v2_validation_public_registration_request(path: str) -> bool:
    return path in {
        "/v2/validation-bots/registrations/invite-code",
        "/v2/validation-bots/registrations/partner-bootstrap",
    }


def _header_or_fallback(request: Request, *, header: str, fallback: str) -> str:
    value = request.headers.get(header)
    if isinstance(value, str) and value.strip():
        return value
    return fallback


@app.middleware("http")
async def platform_api_observability_context_middleware(request: Request, call_next):
    """Attach request correlation identifiers and emit structured request logs."""
    if _is_platform_request(request.url.path):
        request.state.request_id = request.headers.get("X-Request-Id") or f"req-{uuid4()}"
        if _is_v2_validation_request(request.url.path):
            is_public_registration_route = _is_v2_validation_public_registration_request(request.url.path)
            has_auth_headers = bool(
                (request.headers.get("Authorization") or "").strip()
                or (request.headers.get("X-API-Key") or "").strip()
            )
            if is_public_registration_route:
                if has_auth_headers:
                    try:
                        identity = resolve_validation_identity(
                            authorization=request.headers.get("Authorization"),
                            api_key=request.headers.get("X-API-Key"),
                            tenant_header=request.headers.get("X-Tenant-Id"),
                            user_header=request.headers.get("X-User-Id"),
                            request_id=request.state.request_id,
                        )
                    except PlatformAPIError:
                        request.state.tenant_id = "tenant-public-registration"
                        request.state.user_id = "user-public-registration"
                        request.state.user_email_authenticated = False
                        request.state.user_email = None
                    else:
                        request.state.tenant_id = identity.tenant_id
                        request.state.user_id = identity.user_id
                        request.state.user_email_authenticated = True
                        request.state.user_email = identity.user_email
                else:
                    request.state.tenant_id = "tenant-public-registration"
                    request.state.user_id = "user-public-registration"
                    request.state.user_email_authenticated = False
                    request.state.user_email = None
            else:
                try:
                    identity = resolve_validation_identity(
                        authorization=request.headers.get("Authorization"),
                        api_key=request.headers.get("X-API-Key"),
                        tenant_header=request.headers.get("X-Tenant-Id"),
                        user_header=request.headers.get("X-User-Id"),
                        request_id=request.state.request_id,
                    )
                except PlatformAPIError as exc:
                    request.state.tenant_id = "tenant-unauthenticated"
                    request.state.user_id = "user-unauthenticated"
                    log_request_event(
                        logger,
                        level=logging.WARNING,
                        message="Platform API validation request rejected.",
                        request=request,
                        component="api",
                        operation="request_rejected",
                        status_code=exc.status_code,
                        errorCode=exc.code,
                        method=request.method,
                    )
                    return await platform_api_error_handler(request, exc)
                request.state.tenant_id = identity.tenant_id
                request.state.user_id = identity.user_id
                request.state.user_email_authenticated = True
                request.state.user_email = identity.user_email
        else:
            request.state.tenant_id = _header_or_fallback(
                request,
                header="X-Tenant-Id",
                fallback="tenant-local",
            )
            request.state.user_id = _header_or_fallback(
                request,
                header="X-User-Id",
                fallback="user-local",
            )
            raw_user_email = request.headers.get("X-User-Email")
            request.state.user_email_authenticated = False
            request.state.user_email = raw_user_email if isinstance(raw_user_email, str) and raw_user_email.strip() else None
        log_request_event(
            logger,
            level=logging.INFO,
            message="Platform API request started.",
            request=request,
            component="api",
            operation="request_started",
            method=request.method,
        )

    response = await call_next(request)

    if _is_platform_request(request.url.path):
        log_request_event(
            logger,
            level=logging.INFO,
            message="Platform API request completed.",
            request=request,
            component="api",
            operation="request_completed",
            status_code=response.status_code,
            method=request.method,
        )
    return response


@app.middleware("http")
async def platform_api_unhandled_error_middleware(request: Request, call_next):
    """Apply fallback v1 error envelope only to Platform API routes."""
    try:
        return await call_next(request)
    except Exception as exc:
        if _is_platform_request(request.url.path):
            logger.exception(
                "Unhandled exception for Platform API request %s",
                request.url.path,
                extra=request_log_fields(
                    request=request,
                    component="api",
                    operation="request_failed_unhandled",
                ),
            )
            return await unhandled_error_handler(request, exc)
        raise


# Include routes
if legacy_router is not None and lona_router is not None:
    app.include_router(legacy_router, prefix="/api")
    app.include_router(lona_router, prefix="/api")
elif _legacy_router_import_error is not None:
    logger.warning(
        "Optional legacy /api routes disabled because dependency import failed: %s",
        _legacy_router_import_error,
    )
app.include_router(platform_api_v1_router)
app.include_router(platform_api_v2_router)

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

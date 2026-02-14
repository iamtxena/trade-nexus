"""Error helpers for the v1 platform API."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class PlatformAPIError(Exception):
    """Domain error mapped to OpenAPI-compliant error envelopes."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.request_id = request_id


def error_envelope(
    *,
    code: str,
    message: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical ErrorResponse payload."""
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        },
        "requestId": request_id,
    }
    if details is not None:
        payload["error"]["details"] = details
    return payload


async def platform_api_error_handler(request: Request, exc: PlatformAPIError) -> JSONResponse:
    """Convert domain exceptions into canonical JSON error payloads."""
    request_id = exc.request_id or getattr(request.state, "request_id", None) or "req-unknown"
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope(
            code=exc.code,
            message=exc.message,
            request_id=request_id,
            details=exc.details,
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler preserving the OpenAPI error envelope."""
    request_id = getattr(request.state, "request_id", None) or "req-unknown"
    return JSONResponse(
        status_code=500,
        content=error_envelope(
            code="INTERNAL_ERROR",
            message="Internal server error",
            request_id=request_id,
        ),
    )

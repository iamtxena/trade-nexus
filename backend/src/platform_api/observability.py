"""Structured observability helpers for Platform API runtime logs."""

from __future__ import annotations

import logging

from fastapi import Request

from src.platform_api.schemas_v1 import RequestContext


def context_log_fields(
    *,
    context: RequestContext,
    component: str,
    operation: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    status_code: int | None = None,
    **details: object,
) -> dict[str, object]:
    fields: dict[str, object] = {
        "requestId": context.request_id,
        "tenantId": context.tenant_id,
        "userId": context.user_id,
        "component": component,
        "operation": operation,
    }
    if resource_type is not None:
        fields["resourceType"] = resource_type
    if resource_id is not None:
        fields["resourceId"] = resource_id
    if status_code is not None:
        fields["statusCode"] = status_code
    for key, value in details.items():
        if value is None:
            continue
        fields[key] = value
    return fields


def request_log_fields(
    *,
    request: Request,
    component: str,
    operation: str,
    status_code: int | None = None,
    **details: object,
) -> dict[str, object]:
    request_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-Id") or "req-unknown"
    tenant_id = getattr(request.state, "tenant_id", None) or request.headers.get("X-Tenant-Id") or "tenant-local"
    user_id = getattr(request.state, "user_id", None) or request.headers.get("X-User-Id") or "user-local"
    fields: dict[str, object] = {
        "requestId": request_id,
        "tenantId": tenant_id,
        "userId": user_id,
        "component": component,
        "operation": operation,
        "resourceType": "request",
        "resourceId": request.url.path,
    }
    if status_code is not None:
        fields["statusCode"] = status_code
    for key, value in details.items():
        if value is None:
            continue
        fields[key] = value
    return fields


def log_context_event(
    logger: logging.Logger,
    *,
    level: int,
    message: str,
    context: RequestContext,
    component: str,
    operation: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    status_code: int | None = None,
    **details: object,
) -> None:
    logger.log(
        level,
        message,
        extra=context_log_fields(
            context=context,
            component=component,
            operation=operation,
            resource_type=resource_type,
            resource_id=resource_id,
            status_code=status_code,
            **details,
        ),
    )


def log_request_event(
    logger: logging.Logger,
    *,
    level: int,
    message: str,
    request: Request,
    component: str,
    operation: str,
    status_code: int | None = None,
    **details: object,
) -> None:
    logger.log(
        level,
        message,
        extra=request_log_fields(
            request=request,
            component=component,
            operation=operation,
            status_code=status_code,
            **details,
        ),
    )

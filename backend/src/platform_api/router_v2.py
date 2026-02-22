"""FastAPI router for additive Platform API v2 endpoints."""

from __future__ import annotations

import hashlib
import re
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, status

from src.platform_api import router_v1 as router_v1_module
from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import MarketScanRequest, RequestContext
from src.platform_api.schemas_v2 import (
    AcceptValidationInviteRequest,
    BacktestDataExportRequest,
    BacktestDataExportResponse,
    BotKeyMetadata,
    BotKeyMetadataResponse,
    BotKeyRotationResponse,
    BotRegistration,
    BotRegistrationResponse,
    Bot,
    BotIssuedApiKey,
    ConversationSessionResponse,
    ConversationTurnResponse,
    CreateBotInviteRegistrationRequest,
    CreateBotKeyRevocationRequest,
    CreateBotKeyRotationRequest,
    CreateBotPartnerBootstrapRequest,
    CreateConversationSessionRequest,
    CreateConversationTurnRequest,
    CreateValidationBaselineRequest,
    CreateValidationInviteRequest,
    CreateValidationRegressionReplayRequest,
    CreateValidationRenderRequest,
    CreateValidationReviewCommentRequest,
    CreateValidationReviewDecisionRequest,
    CreateValidationReviewRenderRequest,
    CreateValidationRunRequest,
    CreateValidationRunReviewRequest,
    KnowledgePatternListResponse,
    KnowledgeRegimeResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    MarketScanV2Response,
    ValidationInvite,
    ValidationInviteAcceptanceResponse,
    ValidationInviteListResponse,
    ValidationInviteResponse,
    ValidationRunShare,
    ValidationArtifactResponse,
    ValidationBaselineResponse,
    ValidationRegressionReplayResponse,
    ValidationRenderResponse,
    ValidationReviewCommentResponse,
    ValidationReviewDecisionResponse,
    ValidationReviewRenderResponse,
    ValidationReviewRunDetailResponse,
    ValidationReviewRunListResponse,
    ValidationRunListResponse,
    ValidationRunResponse,
    ValidationRunReviewResponse,
)
from src.platform_api.services.conversation_service import ConversationService
from src.platform_api.services.v2_services import (
    DataV2Service,
    KnowledgeV2Service,
    ResearchV2Service,
)
from src.platform_api.services.validation_identity_service import ValidationIdentityService
from src.platform_api.services.validation_v2_service import ValidationV2Service

router = APIRouter(prefix="/v2")

_knowledge_service = KnowledgeV2Service(router_v1_module._knowledge_query_service)
_data_service = DataV2Service(router_v1_module._data_knowledge_adapter)
_research_service = ResearchV2Service(
    strategy_service=router_v1_module._strategy_service,
    query_service=router_v1_module._knowledge_query_service,
    data_adapter=router_v1_module._data_knowledge_adapter,
    store=router_v1_module._store,
)
_conversation_service = ConversationService(store=router_v1_module._store)
_identity_service = ValidationIdentityService(store=router_v1_module._store)
_validation_service = ValidationV2Service(store=router_v1_module._store, identity_service=_identity_service)


async def _request_context(
    request: Request,
    x_request_id: str | None = Header(default=None, alias="X-Request-Id"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> RequestContext:
    state_request_id = getattr(request.state, "request_id", None)
    request_id = x_request_id or (state_request_id if isinstance(state_request_id, str) and state_request_id.strip() else f"req-{uuid4()}")
    request.state.request_id = request_id
    state_tenant_id = getattr(request.state, "tenant_id", None)
    state_user_id = getattr(request.state, "user_id", None)
    tenant_id = state_tenant_id if isinstance(state_tenant_id, str) and state_tenant_id.strip() else "tenant-local"
    user_id = state_user_id if isinstance(state_user_id, str) and state_user_id.strip() else "user-local"

    actor_identity = None
    if _is_validation_request_path(request.url.path):
        try:
            actor_identity = _identity_service.resolve_api_key(
                api_key=x_api_key,
                tenant_id=tenant_id,
                request_id=request_id,
            )
        except PlatformAPIError:
            # If JWT identity is already verified by middleware, malformed bot keys
            # should not preempt the authenticated user context.
            has_bearer_header = bool((request.headers.get("Authorization") or "").strip())
            state_is_api_key_identity = tenant_id.startswith("tenant-apikey-") and user_id.startswith("user-apikey-")
            if has_bearer_header and not state_is_api_key_identity:
                actor_identity = None
            else:
                raise
    owner_user_id = user_id
    actor_type = "user"
    actor_id = user_id
    if actor_identity is not None:
        # Keep run ownership scoped to the human owner while preserving acting bot identity separately.
        tenant_id = actor_identity.tenant_id
        owner_user_id = actor_identity.owner_user_id
        user_id = actor_identity.owner_user_id
        actor_type = actor_identity.actor_type
        actor_id = actor_identity.actor_id

    state_user_email = getattr(request.state, "user_email", None)
    user_email_authenticated = bool(getattr(request.state, "user_email_authenticated", False))
    user_email = state_user_email if user_email_authenticated and isinstance(state_user_email, str) and state_user_email.strip() else None
    if actor_type != "user":
        user_email = None

    request.state.tenant_id = tenant_id
    request.state.user_id = user_id
    context = RequestContext(
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        owner_user_id=owner_user_id,
        actor_type=actor_type,
        actor_id=actor_id,
        user_email=user_email,
    )
    if (
        context.actor_type == "user"
        and context.user_email is not None
        and _identity_service.has_pending_email_invites(
            tenant_id=context.tenant_id,
            email=context.user_email,
        )
    ):
        _identity_service.activate_email_invites(context=context)
    return context


ContextDep = Annotated[RequestContext, Depends(_request_context)]


def _normalized_bot_id(*, bot_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", bot_name.lower().strip()).strip("-")
    return normalized or "runtime-bot"


def _normalized_email(*, email: str, request_id: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise PlatformAPIError(
            status_code=400,
            code="BOT_REGISTRATION_INVALID",
            message="ownerEmail must be a valid address.",
            request_id=request_id,
            details={"ownerEmail": email},
        )
    return normalized


def _bot_registration_path(method: Literal["invite", "partner"]) -> Literal["invite_code_trial", "partner_bootstrap"]:
    if method == "invite":
        return "invite_code_trial"
    return "partner_bootstrap"


def _bot_key_prefix(raw_key: str) -> str:
    return raw_key[:16]


def _is_validation_request_path(path: str) -> bool:
    if not path.startswith("/v2/validation"):
        return False
    # Bot registration/management endpoints are user-authenticated control-plane calls.
    # Do not let runtime bot API keys override verified JWT identity on these routes.
    return not path.startswith("/v2/validation-bots")


def _resolve_idempotency_key(*, context: RequestContext, idempotency_key: str | None) -> str:
    normalized = (idempotency_key or "").strip()
    if normalized:
        return normalized
    return context.request_id


def _scoped_idempotency_key(*, context: RequestContext, key: str) -> str:
    return f"{context.tenant_id}:{context.user_id}:{key}"


def _get_idempotent_response(
    *,
    scope: str,
    context: RequestContext,
    idempotency_key: str | None,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    key = _resolve_idempotency_key(context=context, idempotency_key=idempotency_key)
    scoped_key = _scoped_idempotency_key(context=context, key=key)
    conflict, cached = router_v1_module._store.get_idempotent_response(  # noqa: SLF001
        scope=scope,
        key=scoped_key,
        payload=payload,
    )
    if conflict:
        raise PlatformAPIError(
            status_code=409,
            code="IDEMPOTENCY_KEY_CONFLICT",
            message="Idempotency-Key reused with different payload.",
            request_id=context.request_id,
        )
    return cached


def _save_idempotent_response(
    *,
    scope: str,
    context: RequestContext,
    idempotency_key: str | None,
    payload: dict[str, Any],
    response: dict[str, Any],
) -> None:
    key = _resolve_idempotency_key(context=context, idempotency_key=idempotency_key)
    scoped_key = _scoped_idempotency_key(context=context, key=key)
    router_v1_module._store.save_idempotent_response(  # noqa: SLF001
        scope=scope,
        key=scoped_key,
        payload=payload,
        response=response,
    )


def _to_validation_invite(invite: object) -> ValidationInvite:
    invite_id = getattr(invite, "invite_id")
    run_id = getattr(invite, "run_id")
    invitee_email = getattr(invite, "invitee_email")
    status_value = getattr(invite, "status")
    invited_by_user_id = getattr(invite, "invited_by_user_id")
    invited_by_actor_type = getattr(invite, "invited_by_actor_type")
    created_at = getattr(invite, "created_at")
    expires_at = getattr(invite, "expires_at")
    accepted_at = getattr(invite, "accepted_at")
    revoked_at = getattr(invite, "revoked_at")
    return ValidationInvite(
        id=invite_id,
        runId=run_id,
        email=invitee_email,
        status=status_value,
        invitedByUserId=invited_by_user_id,
        invitedByActorType=invited_by_actor_type,
        createdAt=created_at,
        expiresAt=expires_at,
        acceptedAt=accepted_at,
        revokedAt=revoked_at,
    )


def _to_validation_run_share(invite: object) -> ValidationRunShare:
    status_value = getattr(invite, "status")
    share_status: Literal["active", "revoked"] = "active" if status_value == "accepted" else "revoked"
    granted_at = getattr(invite, "accepted_at") or getattr(invite, "created_at")
    return ValidationRunShare(
        id=f"vshare-{getattr(invite, 'invite_id')}",
        runId=getattr(invite, "run_id"),
        ownerUserId=getattr(invite, "owner_user_id"),
        sharedWithEmail=getattr(invite, "invitee_email"),
        sharedWithUserId=getattr(invite, "accepted_user_id"),
        inviteId=getattr(invite, "invite_id"),
        status=share_status,
        grantedAt=granted_at,
        revokedAt=getattr(invite, "revoked_at"),
    )


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse, tags=["Knowledge"])
async def search_knowledge_v2(
    request: KnowledgeSearchRequest,
    context: ContextDep,
) -> KnowledgeSearchResponse:
    return await _knowledge_service.search(request=request, context=context)


@router.get("/knowledge/patterns", response_model=KnowledgePatternListResponse, tags=["Knowledge"])
async def list_knowledge_patterns_v2(
    context: ContextDep,
    type: str | None = None,
    asset: str | None = None,
    limit: int = 25,
) -> KnowledgePatternListResponse:
    return await _knowledge_service.list_patterns(
        pattern_type=type,
        asset=asset,
        limit=limit,
        context=context,
    )


@router.get("/knowledge/regimes/{asset}", response_model=KnowledgeRegimeResponse, tags=["Knowledge"])
async def get_knowledge_regime_v2(
    asset: str,
    context: ContextDep,
) -> KnowledgeRegimeResponse:
    return await _knowledge_service.get_regime(asset=asset, context=context)


@router.post(
    "/data/exports/backtest",
    response_model=BacktestDataExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Data"],
)
async def create_backtest_data_export_v2(
    request: BacktestDataExportRequest,
    context: ContextDep,
) -> BacktestDataExportResponse:
    return await _data_service.create_backtest_export(request=request, context=context)


@router.get("/data/exports/{exportId}", response_model=BacktestDataExportResponse, tags=["Data"])
async def get_backtest_data_export_v2(
    exportId: str,
    context: ContextDep,
) -> BacktestDataExportResponse:
    return await _data_service.get_backtest_export(export_id=exportId, context=context)


@router.post("/research/market-scan", response_model=MarketScanV2Response, tags=["Research"])
async def post_market_scan_v2(
    request: MarketScanRequest,
    context: ContextDep,
) -> MarketScanV2Response:
    return await _research_service.market_scan(request=request, context=context)


@router.post(
    "/conversations/sessions",
    response_model=ConversationSessionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Conversations"],
)
async def create_conversation_session_v2(
    request: CreateConversationSessionRequest,
    context: ContextDep,
) -> ConversationSessionResponse:
    return await _conversation_service.create_session(request=request, context=context)


@router.get(
    "/conversations/sessions/{sessionId}",
    response_model=ConversationSessionResponse,
    tags=["Conversations"],
)
async def get_conversation_session_v2(
    sessionId: str,
    context: ContextDep,
) -> ConversationSessionResponse:
    return await _conversation_service.get_session(session_id=sessionId, context=context)


@router.post(
    "/conversations/sessions/{sessionId}/turns",
    response_model=ConversationTurnResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Conversations"],
)
async def create_conversation_turn_v2(
    sessionId: str,
    request: CreateConversationTurnRequest,
    context: ContextDep,
) -> ConversationTurnResponse:
    return await _conversation_service.create_turn(session_id=sessionId, request=request, context=context)


@router.get("/validation-runs", response_model=ValidationRunListResponse, tags=["Validation"])
async def list_validation_runs_v2(
    context: ContextDep,
) -> ValidationRunListResponse:
    return await _validation_service.list_validation_runs(context=context)


@router.post(
    "/validation-bots/registrations/invite-code",
    response_model=BotRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Validation"],
    operation_id="registerValidationBotInviteCodeV2",
)
async def register_validation_bot_invite_code_v2(
    payload: CreateBotInviteRegistrationRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> BotRegistrationResponse:
    idempotency_payload = payload.model_dump(mode="json")
    cached = _get_idempotent_response(
        scope="validation_bot_registrations_invite_code",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
    )
    if cached is not None:
        return BotRegistrationResponse.model_validate(cached)

    bot_id = _normalized_bot_id(bot_name=payload.botName)
    result = _identity_service.register_bot(
        context=context,
        bot_id=bot_id,
        invite_code=payload.inviteCode,
        partner_key=None,
        partner_secret=None,
    )
    registration_path = _bot_registration_path(result.registration_method)
    issued_key = BotIssuedApiKey(
        rawKey=result.runtime_bot_key,
        key=BotKeyMetadata(
            id=result.key_id,
            botId=result.bot_id,
            keyPrefix=_bot_key_prefix(result.runtime_bot_key),
            status="active",
            createdAt=result.created_at,
            lastUsedAt=None,
            revokedAt=None,
        ),
    )
    response = BotRegistrationResponse(
        requestId=context.request_id,
        bot=Bot(
            id=result.bot_id,
            tenantId=context.tenant_id,
            ownerUserId=result.owner_user_id,
            name=payload.botName,
            status="active",
            registrationPath=registration_path,
            trialExpiresAt=None,
            metadata=payload.metadata,
            createdAt=result.created_at,
            updatedAt=result.created_at,
        ),
        registration=BotRegistration(
            id=f"botreg-{result.key_id}",
            botId=result.bot_id,
            registrationPath=registration_path,
            status="completed",
            audit={
                "source": "invite_code_trial",
                "inviteCodePrefix": hashlib.sha256(payload.inviteCode.encode("utf-8")).hexdigest()[:10],
                "rateLimitBucket": "bot_invite_trial",
            },
            createdAt=result.created_at,
        ),
        issuedKey=issued_key,
    )
    _save_idempotent_response(
        scope="validation_bot_registrations_invite_code",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
        response=response.model_dump(mode="json"),
    )
    return response


@router.post(
    "/validation-bots/registrations/partner-bootstrap",
    response_model=BotRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Validation"],
    operation_id="registerValidationBotPartnerBootstrapV2",
)
async def register_validation_bot_partner_bootstrap_v2(
    payload: CreateBotPartnerBootstrapRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> BotRegistrationResponse:
    idempotency_payload = payload.model_dump(mode="json")
    cached = _get_idempotent_response(
        scope="validation_bot_registrations_partner_bootstrap",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
    )
    if cached is not None:
        return BotRegistrationResponse.model_validate(cached)

    bot_id = _normalized_bot_id(bot_name=payload.botName)
    owner_email = _normalized_email(email=payload.ownerEmail, request_id=context.request_id)
    registration_context = context
    is_public_registration_identity = (
        context.user_id == "user-public-registration"
        or context.tenant_id == "tenant-public-registration"
    )
    if is_public_registration_identity:
        digest = hashlib.sha256(owner_email.encode("utf-8")).hexdigest()
        derived_user_id = f"user-email-{digest[:12]}"
        derived_tenant_id = f"tenant-email-{digest[12:24]}"
        registration_context = context.model_copy(
            update={
                "tenant_id": derived_tenant_id,
                "user_id": derived_user_id,
                "owner_user_id": derived_user_id,
                "actor_type": "user",
                "actor_id": derived_user_id,
                "user_email": owner_email,
            }
        )
    result = _identity_service.register_bot(
        context=registration_context,
        bot_id=bot_id,
        invite_code=None,
        partner_key=payload.partnerKey,
        partner_secret=payload.partnerSecret,
    )
    registration_path = _bot_registration_path(result.registration_method)
    issued_key = BotIssuedApiKey(
        rawKey=result.runtime_bot_key,
        key=BotKeyMetadata(
            id=result.key_id,
            botId=result.bot_id,
            keyPrefix=_bot_key_prefix(result.runtime_bot_key),
            status="active",
            createdAt=result.created_at,
            lastUsedAt=None,
            revokedAt=None,
        ),
    )
    response = BotRegistrationResponse(
        requestId=context.request_id,
        bot=Bot(
            id=result.bot_id,
            tenantId=registration_context.tenant_id,
            ownerUserId=result.owner_user_id,
            name=payload.botName,
            status="active",
            registrationPath=registration_path,
            trialExpiresAt=None,
            metadata=payload.metadata,
            createdAt=result.created_at,
            updatedAt=result.created_at,
        ),
        registration=BotRegistration(
            id=f"botreg-{result.key_id}",
            botId=result.bot_id,
            registrationPath=registration_path,
            status="completed",
            audit={
                "source": "partner_bootstrap",
                "partnerKeyId": payload.partnerKey,
                "ownerEmail": owner_email,
            },
            createdAt=result.created_at,
        ),
        issuedKey=issued_key,
    )
    _save_idempotent_response(
        scope="validation_bot_registrations_partner_bootstrap",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
        response=response.model_dump(mode="json"),
    )
    return response


@router.post(
    "/validation-bots/{botId}/keys/rotate",
    response_model=BotKeyRotationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Validation"],
    operation_id="rotateValidationBotKeyV2",
)
async def rotate_validation_bot_key_v2(
    botId: str,
    context: ContextDep,
    payload: CreateBotKeyRotationRequest | None = None,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> BotKeyRotationResponse:
    normalized_bot_id = botId.strip().lower()
    idempotency_payload = {
        "botId": normalized_bot_id,
        "request": payload.model_dump(mode="json") if payload is not None else {},
    }
    cached = _get_idempotent_response(
        scope="validation_bot_key_rotations",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
    )
    if cached is not None:
        return BotKeyRotationResponse.model_validate(cached)

    result = _identity_service.rotate_bot_key(
        context=context,
        bot_id=botId,
    )
    response = BotKeyRotationResponse(
        requestId=context.request_id,
        botId=result.bot_id,
        issuedKey=BotIssuedApiKey(
            rawKey=result.runtime_bot_key,
            key=BotKeyMetadata(
                id=result.key_id,
                botId=result.bot_id,
                keyPrefix=_bot_key_prefix(result.runtime_bot_key),
                status="active",
                createdAt=result.created_at,
                lastUsedAt=None,
                revokedAt=None,
            ),
        ),
    )
    _save_idempotent_response(
        scope="validation_bot_key_rotations",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
        response=response.model_dump(mode="json"),
    )
    return response


@router.post(
    "/validation-bots/{botId}/keys/{keyId}/revoke",
    response_model=BotKeyMetadataResponse,
    tags=["Validation"],
    operation_id="revokeValidationBotKeyV2",
)
async def revoke_validation_bot_key_v2(
    botId: str,
    keyId: str,
    context: ContextDep,
    payload: CreateBotKeyRevocationRequest | None = None,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> BotKeyMetadataResponse:
    normalized_bot_id = botId.strip().lower()
    normalized_key_id = keyId.strip()
    idempotency_payload = {
        "botId": normalized_bot_id,
        "keyId": normalized_key_id,
        "request": payload.model_dump(mode="json") if payload is not None else {},
    }
    cached = _get_idempotent_response(
        scope="validation_bot_key_revocations",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
    )
    if cached is not None:
        return BotKeyMetadataResponse.model_validate(cached)

    _identity_service.revoke_bot_key(
        context=context,
        bot_id=botId,
        key_id=normalized_key_id,
    )
    record = _identity_service.get_bot_key(key_id=normalized_key_id)
    if record is None:
        raise PlatformAPIError(
            status_code=404,
            code="BOT_KEY_NOT_FOUND",
            message=f"Runtime bot key {keyId} not found.",
            request_id=context.request_id,
        )
    response = BotKeyMetadataResponse(
        requestId=context.request_id,
        botId=record.bot_id,
        key=BotKeyMetadata(
            id=record.key_id,
            botId=record.bot_id,
            keyPrefix=_bot_key_prefix(f"tnx.bot.{record.bot_id}.{record.key_id}"),
            status="revoked",
            createdAt=record.created_at,
            lastUsedAt=record.last_used_at,
            revokedAt=record.revoked_at,
        ),
    )
    _save_idempotent_response(
        scope="validation_bot_key_revocations",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
        response=response.model_dump(mode="json"),
    )
    return response


@router.post(
    "/validation-runs",
    response_model=ValidationRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def create_validation_run_v2(
    request: CreateValidationRunRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationRunResponse:
    return await _validation_service.create_validation_run(
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.get("/validation-runs/{runId}", response_model=ValidationRunResponse, tags=["Validation"])
async def get_validation_run_v2(
    runId: str,
    context: ContextDep,
) -> ValidationRunResponse:
    return await _validation_service.get_validation_run(run_id=runId, context=context)


@router.get(
    "/validation-runs/{runId}/artifact",
    response_model=ValidationArtifactResponse,
    tags=["Validation"],
)
async def get_validation_run_artifact_v2(
    runId: str,
    context: ContextDep,
) -> ValidationArtifactResponse:
    return await _validation_service.get_validation_run_artifact(run_id=runId, context=context)


@router.post(
    "/validation-runs/{runId}/review",
    response_model=ValidationRunReviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def submit_validation_run_review_v2(
    runId: str,
    request: CreateValidationRunReviewRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationRunReviewResponse:
    return await _validation_service.submit_validation_run_review(
        run_id=runId,
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/validation-runs/{runId}/render",
    response_model=ValidationRenderResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def create_validation_run_render_v2(
    runId: str,
    request: CreateValidationRenderRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationRenderResponse:
    return await _validation_service.create_validation_render(
        run_id=runId,
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.get("/validation-review/runs", response_model=ValidationReviewRunListResponse, tags=["Validation"])
async def list_validation_review_runs_v2(
    context: ContextDep,
    status: Literal["queued", "running", "completed", "failed"] | None = None,
    finalDecision: Literal["pending", "pass", "conditional_pass", "fail"] | None = None,
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
) -> ValidationReviewRunListResponse:
    return await _validation_service.list_validation_review_runs(
        context=context,
        status_filter=status,
        final_decision_filter=finalDecision,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/validation-review/runs/{runId}",
    response_model=ValidationReviewRunDetailResponse,
    tags=["Validation"],
)
async def get_validation_review_run_v2(
    runId: str,
    context: ContextDep,
) -> ValidationReviewRunDetailResponse:
    return await _validation_service.get_validation_review_run(run_id=runId, context=context)


@router.post(
    "/validation-review/runs/{runId}/comments",
    response_model=ValidationReviewCommentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def create_validation_review_comment_v2(
    runId: str,
    request: CreateValidationReviewCommentRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationReviewCommentResponse:
    return await _validation_service.create_validation_review_comment(
        run_id=runId,
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/validation-review/runs/{runId}/decisions",
    response_model=ValidationReviewDecisionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def create_validation_review_decision_v2(
    runId: str,
    request: CreateValidationReviewDecisionRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationReviewDecisionResponse:
    return await _validation_service.create_validation_review_decision(
        run_id=runId,
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/validation-review/runs/{runId}/renders",
    response_model=ValidationReviewRenderResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def create_validation_review_render_v2(
    runId: str,
    request: CreateValidationReviewRenderRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationReviewRenderResponse:
    return await _validation_service.create_validation_review_render(
        run_id=runId,
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.get(
    "/validation-review/runs/{runId}/renders/{format}",
    response_model=ValidationReviewRenderResponse,
    tags=["Validation"],
)
async def get_validation_review_render_v2(
    runId: str,
    format: Literal["html", "pdf"],
    context: ContextDep,
) -> ValidationReviewRenderResponse:
    return await _validation_service.get_validation_review_render(
        run_id=runId,
        format=format,
        context=context,
    )


@router.post(
    "/validation-baselines",
    response_model=ValidationBaselineResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Validation"],
)
async def create_validation_baseline_v2(
    request: CreateValidationBaselineRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationBaselineResponse:
    return await _validation_service.create_validation_baseline(
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/validation-regressions/replay",
    response_model=ValidationRegressionReplayResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Validation"],
)
async def replay_validation_regression_v2(
    request: CreateValidationRegressionReplayRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationRegressionReplayResponse:
    return await _validation_service.replay_validation_regression(
        request=request,
        context=context,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/validation-sharing/runs/{runId}/invites",
    response_model=ValidationInviteResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Validation"],
    operation_id="createValidationRunInviteV2",
)
async def create_validation_run_invite_v2(
    runId: str,
    request: CreateValidationInviteRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationInviteResponse:
    idempotency_payload = {
        "runId": runId,
        "permission": "review",
        "request": request.model_dump(mode="json"),
    }
    cached = _get_idempotent_response(
        scope="validation_run_invites",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
    )
    if cached is not None:
        return ValidationInviteResponse.model_validate(cached)
    invite = await _validation_service.create_validation_run_invite(
        run_id=runId,
        invitee_email=request.email,
        permission="review",
        expires_at=request.expiresAt,
        context=context,
    )
    response = ValidationInviteResponse(
        requestId=context.request_id,
        invite=_to_validation_invite(invite),
    )
    _save_idempotent_response(
        scope="validation_run_invites",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
        response=response.model_dump(mode="json"),
    )
    return response


@router.get(
    "/validation-sharing/runs/{runId}/invites",
    response_model=ValidationInviteListResponse,
    tags=["Validation"],
    operation_id="listValidationRunInvitesV2",
)
async def list_validation_run_invites_v2(
    runId: str,
    context: ContextDep,
    cursor: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
) -> ValidationInviteListResponse:
    offset = 0
    if cursor is not None:
        try:
            offset = int(cursor)
        except ValueError as exc:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_SHARE_INVALID",
                message="cursor must be a non-negative integer offset.",
                request_id=context.request_id,
                details={"cursor": cursor},
            ) from exc
        if offset < 0:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_SHARE_INVALID",
                message="cursor must be a non-negative integer offset.",
                request_id=context.request_id,
                details={"cursor": cursor},
            )
    invites = await _validation_service.list_validation_run_invites(
        run_id=runId,
        context=context,
    )
    page = invites[offset : offset + limit]
    items = [_to_validation_invite(invite) for invite in page]
    next_cursor = str(offset + limit) if (offset + limit) < len(invites) else None
    return ValidationInviteListResponse(
        requestId=context.request_id,
        items=items,
        nextCursor=next_cursor,
    )


@router.post(
    "/validation-sharing/invites/{inviteId}/revoke",
    response_model=ValidationInviteResponse,
    tags=["Validation"],
    operation_id="revokeValidationInviteV2",
)
async def revoke_validation_invite_v2(
    inviteId: str,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationInviteResponse:
    idempotency_payload = {"inviteId": inviteId}
    cached = _get_idempotent_response(
        scope="validation_invite_revocations",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
    )
    if cached is not None:
        return ValidationInviteResponse.model_validate(cached)
    invite = await _validation_service.revoke_validation_invite(
        invite_id=inviteId,
        context=context,
    )
    response = ValidationInviteResponse(
        requestId=context.request_id,
        invite=_to_validation_invite(invite),
    )
    _save_idempotent_response(
        scope="validation_invite_revocations",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
        response=response.model_dump(mode="json"),
    )
    return response


@router.post(
    "/validation-sharing/invites/{inviteId}/accept",
    response_model=ValidationInviteAcceptanceResponse,
    tags=["Validation"],
    operation_id="acceptValidationInviteOnLoginV2",
)
async def accept_validation_invite_on_login_v2(
    inviteId: str,
    request: AcceptValidationInviteRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationInviteAcceptanceResponse:
    idempotency_payload = {
        "inviteId": inviteId,
        "request": request.model_dump(mode="json"),
    }
    cached = _get_idempotent_response(
        scope="validation_invite_acceptance",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
    )
    if cached is not None:
        return ValidationInviteAcceptanceResponse.model_validate(cached)
    invite = await _validation_service.accept_validation_invite_on_login(
        invite_id=inviteId,
        accepted_email=request.acceptedEmail,
        context=context,
    )
    response = ValidationInviteAcceptanceResponse(
        requestId=context.request_id,
        invite=_to_validation_invite(invite),
        share=_to_validation_run_share(invite),
    )
    _save_idempotent_response(
        scope="validation_invite_acceptance",
        context=context,
        idempotency_key=idempotency_key,
        payload=idempotency_payload,
        response=response.model_dump(mode="json"),
    )
    return response


@router.get(
    "/validation-sharing/runs/{runId}",
    response_model=ValidationRunResponse,
    tags=["Shared Validation"],
)
async def get_shared_validation_run_v2(
    runId: str,
    context: ContextDep,
) -> ValidationRunResponse:
    return await _validation_service.get_shared_validation_run(run_id=runId, context=context)


@router.get(
    "/validation-sharing/runs/{runId}/artifact",
    response_model=ValidationArtifactResponse,
    tags=["Shared Validation"],
)
async def get_shared_validation_artifact_v2(
    runId: str,
    context: ContextDep,
) -> ValidationArtifactResponse:
    return await _validation_service.get_shared_validation_run_artifact(run_id=runId, context=context)


@router.post(
    "/validation-sharing/runs/{runId}/review",
    response_model=ValidationRunReviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Shared Validation"],
)
async def submit_shared_validation_review_v2(
    runId: str,
    payload: CreateValidationRunReviewRequest,
    context: ContextDep,
    idempotency_key: str = Header(alias="Idempotency-Key"),
) -> ValidationRunReviewResponse:
    return await _validation_service.submit_shared_validation_run_review(
        run_id=runId,
        request=payload,
        context=context,
        idempotency_key=idempotency_key,
    )

"""Runtime bot identity linkage and shared-validation access controls."""

from __future__ import annotations

import hmac
import json
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import pbkdf2_hmac
from typing import Any, Literal

from src.platform_api.errors import PlatformAPIError
from src.platform_api.schemas_v1 import RequestContext
from src.platform_api.state_store import InMemoryStateStore, ValidationIdentityAuditRecord, utc_now

logger = logging.getLogger(__name__)

ActorType = Literal["user", "bot"]
RegistrationMethod = Literal["invite", "partner"]
SharePermission = Literal["view", "review"]
ShareInviteStatus = Literal["pending", "accepted", "revoked", "expired"]


@dataclass(frozen=True)
class RuntimeActorIdentity:
    tenant_id: str
    owner_user_id: str
    actor_type: ActorType
    actor_id: str


@dataclass(frozen=True)
class BotInviteCodeRecord:
    invite_id: str
    tenant_id: str
    owner_user_id: str
    bot_id: str
    code_hash: str
    code_salt: str
    created_at: str
    expires_at: str
    created_by_ip: str
    used_at: str | None = None
    revoked_at: str | None = None

    @property
    def used(self) -> bool:
        return self.used_at is not None

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None


@dataclass(frozen=True)
class BotRuntimeKeyRecord:
    key_id: str
    tenant_id: str
    owner_user_id: str
    bot_id: str
    secret_hash: str
    secret_salt: str
    created_at: str
    registration_method: RegistrationMethod
    revoked_at: str | None = None
    last_used_at: str | None = None

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None


@dataclass(frozen=True)
class BotRegistrationResult:
    bot_id: str
    owner_user_id: str
    actor_type: Literal["bot"]
    actor_id: str
    key_id: str
    runtime_bot_key: str
    registration_method: RegistrationMethod
    created_at: str


@dataclass(frozen=True)
class SharedValidationInviteRecord:
    invite_id: str
    run_id: str
    tenant_id: str
    owner_user_id: str
    invitee_email: str
    permission: SharePermission
    status: ShareInviteStatus
    invited_by_user_id: str
    invited_by_actor_type: ActorType
    created_at: str
    expires_at: str | None = None
    revoked_at: str | None = None
    accepted_user_id: str | None = None
    accepted_at: str | None = None


class ValidationIdentityService:
    """Owns runtime bot identity, bot-key resolution, and run-share invite state."""

    _RUNTIME_KEY_PREFIX = "tnx.bot"
    _INVITE_CODE_TOKEN_BYTES = 24
    _SECRET_HASH_ITERATIONS = 240_000
    _SECRET_HASH_BYTES = 32

    def __init__(
        self,
        *,
        store: InMemoryStateStore,
        invite_rate_limit: int = 3,
        invite_window_seconds: int = 3600,
        invite_ttl_seconds: int = 3600,
        partner_credentials: dict[str, str] | None = None,
    ) -> None:
        self._store = store
        self._invite_rate_limit = invite_rate_limit
        self._invite_window_seconds = invite_window_seconds
        self._invite_ttl_seconds = invite_ttl_seconds
        self._partner_credentials = partner_credentials if partner_credentials is not None else _load_partner_credentials()

        self._invite_codes: dict[str, BotInviteCodeRecord] = {}
        self._bot_keys: dict[str, BotRuntimeKeyRecord] = {}
        self._bot_key_index: dict[tuple[str, str, str], set[str]] = {}
        self._invite_rate_limit_index: dict[str, list[float]] = {}

        self._share_invites_by_run: dict[str, list[SharedValidationInviteRecord]] = {}
        self._share_grants_by_run: dict[str, dict[str, SharePermission]] = {}
        self._pending_share_invite_index: dict[tuple[str, str], dict[str, int]] = {}

        self._invite_counter = 1
        self._key_counter = 1
        self._share_counter = 1

    def request_invite_code(
        self,
        *,
        context: RequestContext,
        bot_id: str,
        source_ip: str,
    ) -> tuple[str, str]:
        try:
            normalized_bot_id = _normalize_bot_id(bot_id)
        except ValueError as exc:
            raise PlatformAPIError(
                status_code=400,
                code="BOT_REGISTRATION_INVALID",
                message=str(exc),
                request_id=context.request_id,
                details={"botId": bot_id},
            ) from exc
        normalized_ip = source_ip.strip() if source_ip.strip() else "unknown"
        if not self._allow_invite_request(normalized_ip):
            raise PlatformAPIError(
                status_code=429,
                code="BOT_INVITE_RATE_LIMITED",
                message="Too many invite-code requests. Try again later.",
                request_id=context.request_id,
                details={"sourceIp": normalized_ip},
            )

        invite_id = f"botinv-{self._invite_counter:06d}"
        self._invite_counter += 1

        # 24 random bytes -> 192-bit invite entropy before prefixing.
        invite_code = f"tnx_invite_{secrets.token_hex(self._INVITE_CODE_TOKEN_BYTES)}"
        salt = secrets.token_hex(16)
        now_dt = datetime.now(tz=UTC)
        expires_dt = now_dt + timedelta(seconds=self._invite_ttl_seconds)

        self._invite_codes[invite_id] = BotInviteCodeRecord(
            invite_id=invite_id,
            tenant_id=context.tenant_id,
            owner_user_id=context.user_id,
            bot_id=normalized_bot_id,
            code_hash=_hash_secret(secret=invite_code, salt=salt),
            code_salt=salt,
            created_at=_to_utc(now_dt),
            expires_at=_to_utc(expires_dt),
            created_by_ip=normalized_ip,
        )
        return invite_code, _to_utc(expires_dt)

    def register_bot(
        self,
        *,
        context: RequestContext,
        bot_id: str,
        invite_code: str | None,
        partner_key: str | None,
        partner_secret: str | None,
    ) -> BotRegistrationResult:
        try:
            normalized_bot_id = _normalize_bot_id(bot_id)
        except ValueError as exc:
            raise PlatformAPIError(
                status_code=400,
                code="BOT_REGISTRATION_INVALID",
                message=str(exc),
                request_id=context.request_id,
                details={"botId": bot_id},
            ) from exc
        method = self._resolve_registration_method(
            invite_code=invite_code,
            partner_key=partner_key,
            partner_secret=partner_secret,
            context=context,
            bot_id=normalized_bot_id,
        )

        existing_key_ids = sorted(self._bot_key_index.get((context.tenant_id, context.user_id, normalized_bot_id), set()))
        rotated_key_ids: list[str] = []
        now = utc_now()
        for key_id in existing_key_ids:
            record = self._bot_keys[key_id]
            if record.revoked:
                continue
            self._bot_keys[key_id] = BotRuntimeKeyRecord(
                key_id=record.key_id,
                tenant_id=record.tenant_id,
                owner_user_id=record.owner_user_id,
                bot_id=record.bot_id,
                secret_hash=record.secret_hash,
                secret_salt=record.secret_salt,
                created_at=record.created_at,
                registration_method=record.registration_method,
                revoked_at=now,
                last_used_at=record.last_used_at,
            )
            rotated_key_ids.append(key_id)

        if rotated_key_ids:
            self._record_audit(
                event_type="rotate",
                request_id=context.request_id,
                tenant_id=context.tenant_id,
                owner_user_id=context.user_id,
                actor_type="user",
                actor_id=context.user_id,
                metadata={
                    "botId": normalized_bot_id,
                    "rotatedKeyIds": rotated_key_ids,
                },
            )

        key_id = f"botkey-{self._key_counter:06d}"
        self._key_counter += 1
        secret = secrets.token_hex(20)
        salt = secrets.token_hex(16)

        self._bot_keys[key_id] = BotRuntimeKeyRecord(
            key_id=key_id,
            tenant_id=context.tenant_id,
            owner_user_id=context.user_id,
            bot_id=normalized_bot_id,
            secret_hash=_hash_secret(secret=secret, salt=salt),
            secret_salt=salt,
            created_at=now,
            registration_method=method,
        )
        self._bot_key_index.setdefault((context.tenant_id, context.user_id, normalized_bot_id), set()).add(key_id)

        self._record_audit(
            event_type="register",
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            owner_user_id=context.user_id,
            actor_type="user",
            actor_id=context.user_id,
            metadata={
                "botId": normalized_bot_id,
                "keyId": key_id,
                "method": method,
            },
        )

        return BotRegistrationResult(
            bot_id=normalized_bot_id,
            owner_user_id=context.user_id,
            actor_type="bot",
            actor_id=normalized_bot_id,
            key_id=key_id,
            runtime_bot_key=f"{self._RUNTIME_KEY_PREFIX}.{normalized_bot_id}.{key_id}.{secret}",
            registration_method=method,
            created_at=now,
        )

    def revoke_bot_key(
        self,
        *,
        context: RequestContext,
        bot_id: str,
        key_id: str | None,
    ) -> list[str]:
        try:
            normalized_bot_id = _normalize_bot_id(bot_id)
        except ValueError as exc:
            raise PlatformAPIError(
                status_code=400,
                code="BOT_REGISTRATION_INVALID",
                message=str(exc),
                request_id=context.request_id,
                details={"botId": bot_id},
            ) from exc
        candidate_key_ids = sorted(self._bot_key_index.get((context.tenant_id, context.user_id, normalized_bot_id), set()))
        if key_id is not None:
            normalized_key_id = key_id.strip()
            candidate_key_ids = [item for item in candidate_key_ids if item == normalized_key_id]

        revoked: list[str] = []
        now = utc_now()
        for candidate in candidate_key_ids:
            record = self._bot_keys[candidate]
            if record.revoked:
                continue
            self._bot_keys[candidate] = BotRuntimeKeyRecord(
                key_id=record.key_id,
                tenant_id=record.tenant_id,
                owner_user_id=record.owner_user_id,
                bot_id=record.bot_id,
                secret_hash=record.secret_hash,
                secret_salt=record.secret_salt,
                created_at=record.created_at,
                registration_method=record.registration_method,
                revoked_at=now,
                last_used_at=record.last_used_at,
            )
            revoked.append(candidate)

        if not revoked:
            raise PlatformAPIError(
                status_code=404,
                code="BOT_KEY_NOT_FOUND",
                message="No active runtime bot key found for revoke request.",
                request_id=context.request_id,
                details={"botId": normalized_bot_id, "keyId": key_id},
            )

        self._record_audit(
            event_type="revoke",
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            owner_user_id=context.user_id,
            actor_type="user",
            actor_id=context.user_id,
            metadata={
                "botId": normalized_bot_id,
                "revokedKeyIds": revoked,
            },
        )
        return revoked

    def rotate_bot_key(
        self,
        *,
        context: RequestContext,
        bot_id: str,
    ) -> BotRegistrationResult:
        try:
            normalized_bot_id = _normalize_bot_id(bot_id)
        except ValueError as exc:
            raise PlatformAPIError(
                status_code=400,
                code="BOT_REGISTRATION_INVALID",
                message=str(exc),
                request_id=context.request_id,
                details={"botId": bot_id},
            ) from exc
        candidate_key_ids = sorted(self._bot_key_index.get((context.tenant_id, context.user_id, normalized_bot_id), set()))
        active_key_ids = [item for item in candidate_key_ids if not self._bot_keys[item].revoked]
        if not active_key_ids:
            raise PlatformAPIError(
                status_code=404,
                code="BOT_KEY_NOT_FOUND",
                message="No active runtime bot key found for rotation.",
                request_id=context.request_id,
                details={"botId": normalized_bot_id},
            )

        now = utc_now()
        registration_method = self._bot_keys[active_key_ids[-1]].registration_method
        for key_id in active_key_ids:
            record = self._bot_keys[key_id]
            self._bot_keys[key_id] = BotRuntimeKeyRecord(
                key_id=record.key_id,
                tenant_id=record.tenant_id,
                owner_user_id=record.owner_user_id,
                bot_id=record.bot_id,
                secret_hash=record.secret_hash,
                secret_salt=record.secret_salt,
                created_at=record.created_at,
                registration_method=record.registration_method,
                revoked_at=now,
                last_used_at=record.last_used_at,
            )

        key_id = f"botkey-{self._key_counter:06d}"
        self._key_counter += 1
        secret = secrets.token_hex(20)
        salt = secrets.token_hex(16)
        self._bot_keys[key_id] = BotRuntimeKeyRecord(
            key_id=key_id,
            tenant_id=context.tenant_id,
            owner_user_id=context.user_id,
            bot_id=normalized_bot_id,
            secret_hash=_hash_secret(secret=secret, salt=salt),
            secret_salt=salt,
            created_at=now,
            registration_method=registration_method,
        )
        self._bot_key_index.setdefault((context.tenant_id, context.user_id, normalized_bot_id), set()).add(key_id)

        self._record_audit(
            event_type="rotate",
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            owner_user_id=context.user_id,
            actor_type="user",
            actor_id=context.user_id,
            metadata={
                "botId": normalized_bot_id,
                "rotatedKeyIds": active_key_ids,
                "issuedKeyId": key_id,
            },
        )

        return BotRegistrationResult(
            bot_id=normalized_bot_id,
            owner_user_id=context.user_id,
            actor_type="bot",
            actor_id=normalized_bot_id,
            key_id=key_id,
            runtime_bot_key=f"{self._RUNTIME_KEY_PREFIX}.{normalized_bot_id}.{key_id}.{secret}",
            registration_method=registration_method,
            created_at=now,
        )

    def get_bot_key(self, *, key_id: str) -> BotRuntimeKeyRecord | None:
        return self._bot_keys.get(key_id)

    def resolve_api_key(
        self,
        *,
        api_key: str | None,
        tenant_id: str | None,
        request_id: str,
    ) -> RuntimeActorIdentity | None:
        normalized = (api_key or "").strip()
        if normalized == "":
            return None
        if not normalized.startswith(f"{self._RUNTIME_KEY_PREFIX}."):
            return None

        parts = normalized.split(".")
        if len(parts) != 5:
            raise PlatformAPIError(
                status_code=401,
                code="BOT_API_KEY_INVALID",
                message="Runtime bot key format is invalid.",
                request_id=request_id,
            )
        _, _, bot_id, key_id, secret = parts
        record = self._bot_keys.get(key_id)
        if record is None or record.bot_id != bot_id:
            raise PlatformAPIError(
                status_code=401,
                code="BOT_API_KEY_INVALID",
                message="Runtime bot key is invalid.",
                request_id=request_id,
            )
        normalized_tenant_id = (tenant_id or "").strip()
        if (
            normalized_tenant_id
            and normalized_tenant_id != record.tenant_id
            and not normalized_tenant_id.startswith("tenant-apikey-")
        ):
            raise PlatformAPIError(
                status_code=401,
                code="BOT_API_KEY_INVALID",
                message="Runtime bot key is invalid.",
                request_id=request_id,
            )
        actual_hash = _hash_secret(secret=secret, salt=record.secret_salt)
        if not hmac.compare_digest(actual_hash, record.secret_hash):
            raise PlatformAPIError(
                status_code=401,
                code="BOT_API_KEY_INVALID",
                message="Runtime bot key is invalid.",
                request_id=request_id,
            )
        if record.revoked:
            raise PlatformAPIError(
                status_code=401,
                code="BOT_API_KEY_REVOKED",
                message="Runtime bot key has been revoked.",
                request_id=request_id,
            )

        self._bot_keys[key_id] = BotRuntimeKeyRecord(
            key_id=record.key_id,
            tenant_id=record.tenant_id,
            owner_user_id=record.owner_user_id,
            bot_id=record.bot_id,
            secret_hash=record.secret_hash,
            secret_salt=record.secret_salt,
            created_at=record.created_at,
            registration_method=record.registration_method,
            revoked_at=record.revoked_at,
            last_used_at=utc_now(),
        )
        return RuntimeActorIdentity(
            tenant_id=record.tenant_id,
            owner_user_id=record.owner_user_id,
            actor_type="bot",
            actor_id=record.bot_id,
        )

    def create_run_share_invite(
        self,
        *,
        context: RequestContext,
        run_id: str,
        owner_user_id: str,
        invitee_email: str,
        permission: SharePermission,
        expires_at: str | None = None,
    ) -> SharedValidationInviteRecord:
        try:
            normalized_email = _normalize_email(invitee_email)
        except ValueError as exc:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_SHARE_INVALID",
                message=str(exc),
                request_id=context.request_id,
                details={"email": invitee_email},
            ) from exc
        if permission not in {"view", "review"}:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_SHARE_INVALID",
                message="permission must be one of: view, review.",
                request_id=context.request_id,
                details={"permission": permission},
            )
        resolved_expires_at = _resolve_share_invite_expiration(
            expires_at=expires_at,
            request_id=context.request_id,
        )

        invites = self._share_invites_by_run.get(run_id, [])
        for index, existing in enumerate(invites):
            refreshed = self._refresh_expired_share_invite(invite=existing)
            if refreshed is not existing:
                invites[index] = refreshed
            if refreshed.tenant_id != context.tenant_id:
                continue
            if refreshed.owner_user_id != owner_user_id:
                continue
            if refreshed.status != "pending":
                continue
            if refreshed.invitee_email != normalized_email:
                continue
            raise PlatformAPIError(
                status_code=409,
                code="VALIDATION_INVITE_CONFLICT",
                message="A pending invite already exists for this email.",
                request_id=context.request_id,
                details={
                    "runId": run_id,
                    "email": normalized_email,
                    "inviteId": refreshed.invite_id,
                },
            )

        invite_id = f"valshare-{self._share_counter:06d}"
        self._share_counter += 1
        record = SharedValidationInviteRecord(
            invite_id=invite_id,
            run_id=run_id,
            tenant_id=context.tenant_id,
            owner_user_id=owner_user_id,
            invitee_email=normalized_email,
            permission=permission,
            status="pending",
            invited_by_user_id=context.user_id,
            invited_by_actor_type=context.actor_type,
            created_at=utc_now(),
            expires_at=resolved_expires_at,
        )
        self._share_invites_by_run.setdefault(run_id, []).append(record)
        self._index_pending_share_invite(invite=record)

        self._record_audit(
            event_type="share",
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            owner_user_id=owner_user_id,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            metadata={
                "runId": run_id,
                "inviteId": invite_id,
                "inviteeEmail": normalized_email,
                "permission": permission,
            },
        )
        return record

    def list_run_share_invites(
        self,
        *,
        context: RequestContext,
        run_id: str,
        owner_user_id: str,
    ) -> list[SharedValidationInviteRecord]:
        invites = self._share_invites_by_run.get(run_id, [])
        visible: list[SharedValidationInviteRecord] = []
        for index, invite in enumerate(invites):
            refreshed = self._refresh_expired_share_invite(invite=invite)
            if refreshed is not invite:
                invites[index] = refreshed
            if refreshed.tenant_id == context.tenant_id and refreshed.owner_user_id == owner_user_id:
                visible.append(refreshed)
        return visible

    def revoke_run_share_invite(
        self,
        *,
        context: RequestContext,
        invite_id: str,
    ) -> SharedValidationInviteRecord:
        lookup = self._find_share_invite(invite_id=invite_id)
        if lookup is None:
            raise PlatformAPIError(
                status_code=404,
                code="VALIDATION_INVITE_NOT_FOUND",
                message=f"Validation invite {invite_id} not found.",
                request_id=context.request_id,
            )
        run_id, index, invite = lookup
        refreshed_invite = self._refresh_expired_share_invite(invite=invite)
        if refreshed_invite is not invite:
            self._share_invites_by_run[run_id][index] = refreshed_invite
            invite = refreshed_invite
        if invite.tenant_id != context.tenant_id or invite.owner_user_id != context.user_id:
            raise PlatformAPIError(
                status_code=404,
                code="VALIDATION_INVITE_NOT_FOUND",
                message=f"Validation invite {invite_id} not found.",
                request_id=context.request_id,
            )
        if invite.status == "revoked":
            raise PlatformAPIError(
                status_code=409,
                code="VALIDATION_INVITE_STATE_INVALID",
                message=f"Validation invite {invite_id} is already revoked.",
                request_id=context.request_id,
            )
        if invite.status == "expired":
            raise PlatformAPIError(
                status_code=409,
                code="VALIDATION_INVITE_EXPIRED",
                message=f"Validation invite {invite_id} has expired.",
                request_id=context.request_id,
            )
        if invite.status == "pending":
            self._remove_pending_share_invite_index(invite=invite)

        now = utc_now()
        updated = SharedValidationInviteRecord(
            invite_id=invite.invite_id,
            run_id=invite.run_id,
            tenant_id=invite.tenant_id,
            owner_user_id=invite.owner_user_id,
            invitee_email=invite.invitee_email,
            permission=invite.permission,
            status="revoked",
            invited_by_user_id=invite.invited_by_user_id,
            invited_by_actor_type=invite.invited_by_actor_type,
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            revoked_at=now,
            accepted_user_id=invite.accepted_user_id,
            accepted_at=invite.accepted_at,
        )
        self._share_invites_by_run[run_id][index] = updated
        if invite.accepted_user_id is not None:
            self._recalculate_run_grants_for_user(run_id=run_id, user_id=invite.accepted_user_id)

        self._record_audit(
            event_type="revoke",
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            owner_user_id=invite.owner_user_id,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            metadata={
                "runId": run_id,
                "inviteId": invite.invite_id,
                "inviteeEmail": invite.invitee_email,
            },
        )
        return updated

    def accept_run_share_invite(
        self,
        *,
        context: RequestContext,
        invite_id: str,
        accepted_email: str,
    ) -> SharedValidationInviteRecord:
        lookup = self._find_share_invite(invite_id=invite_id)
        if lookup is None:
            raise PlatformAPIError(
                status_code=404,
                code="VALIDATION_INVITE_NOT_FOUND",
                message=f"Validation invite {invite_id} not found.",
                request_id=context.request_id,
            )
        run_id, index, invite = lookup
        if invite.tenant_id != context.tenant_id:
            raise PlatformAPIError(
                status_code=404,
                code="VALIDATION_INVITE_NOT_FOUND",
                message=f"Validation invite {invite_id} not found.",
                request_id=context.request_id,
            )

        authenticated_email = context.user_email
        if authenticated_email is None:
            raise PlatformAPIError(
                status_code=403,
                code="VALIDATION_INVITE_EMAIL_MISMATCH",
                message="Invite acceptance requires authenticated email identity.",
                request_id=context.request_id,
            )
        try:
            normalized_authenticated_email = _normalize_email(authenticated_email)
            normalized_accepted_email = _normalize_email(accepted_email)
        except ValueError as exc:
            raise PlatformAPIError(
                status_code=400,
                code="VALIDATION_SHARE_INVALID",
                message=str(exc),
                request_id=context.request_id,
            ) from exc

        if normalized_authenticated_email != normalized_accepted_email:
            raise PlatformAPIError(
                status_code=403,
                code="VALIDATION_INVITE_EMAIL_MISMATCH",
                message="acceptedEmail does not match authenticated email identity.",
                request_id=context.request_id,
            )
        if invite.invitee_email != normalized_authenticated_email:
            raise PlatformAPIError(
                status_code=403,
                code="VALIDATION_INVITE_EMAIL_MISMATCH",
                message="Invite email does not match authenticated email identity.",
                request_id=context.request_id,
            )
        if invite.status == "revoked":
            raise PlatformAPIError(
                status_code=409,
                code="VALIDATION_INVITE_STATE_INVALID",
                message=f"Validation invite {invite_id} is revoked.",
                request_id=context.request_id,
            )
        if invite.status == "expired":
            raise PlatformAPIError(
                status_code=409,
                code="VALIDATION_INVITE_EXPIRED",
                message=f"Validation invite {invite_id} has expired.",
                request_id=context.request_id,
            )
        if invite.status == "accepted":
            if invite.accepted_user_id == context.user_id:
                return invite
            raise PlatformAPIError(
                status_code=409,
                code="VALIDATION_INVITE_STATE_INVALID",
                message=f"Validation invite {invite_id} was already accepted by another user identity.",
                request_id=context.request_id,
            )
        if _invite_expired(invite.expires_at):
            self._remove_pending_share_invite_index(invite=invite)
            self._share_invites_by_run[run_id][index] = SharedValidationInviteRecord(
                invite_id=invite.invite_id,
                run_id=invite.run_id,
                tenant_id=invite.tenant_id,
                owner_user_id=invite.owner_user_id,
                invitee_email=invite.invitee_email,
                permission=invite.permission,
                status="expired",
                invited_by_user_id=invite.invited_by_user_id,
                invited_by_actor_type=invite.invited_by_actor_type,
                created_at=invite.created_at,
                expires_at=invite.expires_at,
                revoked_at=invite.revoked_at,
                accepted_user_id=invite.accepted_user_id,
                accepted_at=invite.accepted_at,
            )
            raise PlatformAPIError(
                status_code=409,
                code="VALIDATION_INVITE_EXPIRED",
                message=f"Validation invite {invite_id} has expired.",
                request_id=context.request_id,
            )

        self._remove_pending_share_invite_index(invite=invite)
        now = utc_now()
        updated = SharedValidationInviteRecord(
            invite_id=invite.invite_id,
            run_id=invite.run_id,
            tenant_id=invite.tenant_id,
            owner_user_id=invite.owner_user_id,
            invitee_email=invite.invitee_email,
            permission=invite.permission,
            status="accepted",
            invited_by_user_id=invite.invited_by_user_id,
            invited_by_actor_type=invite.invited_by_actor_type,
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            revoked_at=invite.revoked_at,
            accepted_user_id=context.user_id,
            accepted_at=now,
        )
        self._share_invites_by_run[run_id][index] = updated
        existing = self._share_grants_by_run.setdefault(run_id, {}).get(context.user_id)
        self._share_grants_by_run.setdefault(run_id, {})[context.user_id] = _max_permission(existing, updated.permission)

        self._record_audit(
            event_type="accept",
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            owner_user_id=invite.owner_user_id,
            actor_type=context.actor_type,
            actor_id=context.actor_id,
            metadata={
                "runId": run_id,
                "inviteId": invite.invite_id,
                "inviteeEmail": invite.invitee_email,
                "grantedToUserId": context.user_id,
                "permission": updated.permission,
            },
        )
        return updated

    def has_pending_email_invites(self, *, tenant_id: str, email: str | None) -> bool:
        if email is None:
            return False
        try:
            normalized_email = _normalize_email(email)
        except ValueError:
            return False
        return bool(self._pending_share_invite_index.get((tenant_id, normalized_email)))

    def activate_email_invites(self, *, context: RequestContext) -> list[SharedValidationInviteRecord]:
        if context.user_email is None:
            return []

        try:
            normalized_email = _normalize_email(context.user_email)
        except ValueError:
            return []
        accepted: list[SharedValidationInviteRecord] = []
        run_ids = sorted(self._pending_share_invite_index.get((context.tenant_id, normalized_email), {}).keys())
        for run_id in run_ids:
            invites = self._share_invites_by_run.get(run_id, [])
            for index, invite in enumerate(invites):
                if invite.status != "pending":
                    continue
                if invite.tenant_id != context.tenant_id or invite.invitee_email != normalized_email:
                    continue
                if _invite_expired(invite.expires_at):
                    refreshed = self._refresh_expired_share_invite(invite=invite)
                    if refreshed is not invite:
                        invites[index] = refreshed
                    continue

                self._remove_pending_share_invite_index(invite=invite)
                updated = SharedValidationInviteRecord(
                    invite_id=invite.invite_id,
                    run_id=invite.run_id,
                    tenant_id=invite.tenant_id,
                    owner_user_id=invite.owner_user_id,
                    invitee_email=invite.invitee_email,
                    permission=invite.permission,
                    status="accepted",
                    invited_by_user_id=invite.invited_by_user_id,
                    invited_by_actor_type=invite.invited_by_actor_type,
                    created_at=invite.created_at,
                    expires_at=invite.expires_at,
                    revoked_at=invite.revoked_at,
                    accepted_user_id=context.user_id,
                    accepted_at=utc_now(),
                )
                invites[index] = updated

                existing = self._share_grants_by_run.setdefault(run_id, {}).get(context.user_id)
                self._share_grants_by_run.setdefault(run_id, {})[context.user_id] = _max_permission(existing, updated.permission)
                accepted.append(updated)

                self._record_audit(
                    event_type="accept",
                    request_id=context.request_id,
                    tenant_id=context.tenant_id,
                    owner_user_id=invite.owner_user_id,
                    actor_type=context.actor_type,
                    actor_id=context.actor_id,
                    metadata={
                        "runId": run_id,
                        "inviteId": invite.invite_id,
                        "inviteeEmail": invite.invitee_email,
                        "grantedToUserId": context.user_id,
                        "permission": updated.permission,
                    },
                )
        return accepted

    def can_access_run(
        self,
        *,
        run_id: str,
        tenant_id: str,
        run_tenant_id: str,
        owner_user_id: str,
        user_id: str,
        required_permission: SharePermission,
    ) -> bool:
        if tenant_id != run_tenant_id:
            return False
        if user_id == owner_user_id:
            return True

        grants = self._share_grants_by_run.get(run_id)
        if grants is None:
            return False
        permission = grants.get(user_id)
        if permission is None:
            return False

        if required_permission == "view":
            return permission in {"view", "review"}
        return permission == "review"

    def _index_pending_share_invite(self, *, invite: SharedValidationInviteRecord) -> None:
        if invite.status != "pending":
            return
        key = (invite.tenant_id, invite.invitee_email)
        run_counts = self._pending_share_invite_index.setdefault(key, {})
        run_counts[invite.run_id] = run_counts.get(invite.run_id, 0) + 1

    def _remove_pending_share_invite_index(self, *, invite: SharedValidationInviteRecord) -> None:
        key = (invite.tenant_id, invite.invitee_email)
        run_counts = self._pending_share_invite_index.get(key)
        if run_counts is None:
            return
        count = run_counts.get(invite.run_id, 0)
        if count <= 1:
            run_counts.pop(invite.run_id, None)
        else:
            run_counts[invite.run_id] = count - 1
        if not run_counts:
            self._pending_share_invite_index.pop(key, None)

    def _refresh_expired_share_invite(self, *, invite: SharedValidationInviteRecord) -> SharedValidationInviteRecord:
        if invite.status != "pending":
            return invite
        if not _invite_expired(invite.expires_at):
            return invite
        self._remove_pending_share_invite_index(invite=invite)
        return SharedValidationInviteRecord(
            invite_id=invite.invite_id,
            run_id=invite.run_id,
            tenant_id=invite.tenant_id,
            owner_user_id=invite.owner_user_id,
            invitee_email=invite.invitee_email,
            permission=invite.permission,
            status="expired",
            invited_by_user_id=invite.invited_by_user_id,
            invited_by_actor_type=invite.invited_by_actor_type,
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            revoked_at=invite.revoked_at,
            accepted_user_id=invite.accepted_user_id,
            accepted_at=invite.accepted_at,
        )

    def _resolve_registration_method(
        self,
        *,
        invite_code: str | None,
        partner_key: str | None,
        partner_secret: str | None,
        context: RequestContext,
        bot_id: str,
    ) -> RegistrationMethod:
        normalized_invite = (invite_code or "").strip()
        normalized_partner_key = (partner_key or "").strip()
        normalized_partner_secret = (partner_secret or "").strip()

        using_invite = normalized_invite != ""
        using_partner = normalized_partner_key != "" or normalized_partner_secret != ""

        if using_invite and using_partner:
            raise PlatformAPIError(
                status_code=400,
                code="BOT_REGISTRATION_INVALID",
                message="Provide inviteCode or partner credentials, not both.",
                request_id=context.request_id,
            )

        if using_invite:
            self._consume_invite_code(
                invite_code=normalized_invite,
                tenant_id=context.tenant_id,
                owner_user_id=context.user_id,
                bot_id=bot_id,
                request_id=context.request_id,
            )
            return "invite"

        if normalized_partner_key == "" or normalized_partner_secret == "":
            raise PlatformAPIError(
                status_code=400,
                code="BOT_REGISTRATION_INVALID",
                message="Registration requires inviteCode or both partnerKey and partnerSecret.",
                request_id=context.request_id,
            )

        expected_secret = self._partner_credentials.get(normalized_partner_key)
        if expected_secret is None or not hmac.compare_digest(expected_secret, normalized_partner_secret):
            raise PlatformAPIError(
                status_code=401,
                code="BOT_PARTNER_AUTH_INVALID",
                message="Partner credentials are invalid.",
                request_id=context.request_id,
            )
        return "partner"

    def _consume_invite_code(
        self,
        *,
        invite_code: str,
        tenant_id: str,
        owner_user_id: str,
        bot_id: str,
        request_id: str,
    ) -> None:
        now_dt = datetime.now(tz=UTC)
        for invite_id, record in self._invite_codes.items():
            if record.tenant_id != tenant_id:
                continue
            if record.owner_user_id != owner_user_id:
                continue
            if record.bot_id != bot_id:
                continue
            if record.used or record.revoked:
                continue
            if datetime.fromisoformat(record.expires_at.replace("Z", "+00:00")) <= now_dt:
                continue
            expected_hash = _hash_secret(secret=invite_code, salt=record.code_salt)
            if not hmac.compare_digest(expected_hash, record.code_hash):
                continue

            self._invite_codes[invite_id] = BotInviteCodeRecord(
                invite_id=record.invite_id,
                tenant_id=record.tenant_id,
                owner_user_id=record.owner_user_id,
                bot_id=record.bot_id,
                code_hash=record.code_hash,
                code_salt=record.code_salt,
                created_at=record.created_at,
                expires_at=record.expires_at,
                created_by_ip=record.created_by_ip,
                used_at=utc_now(),
                revoked_at=record.revoked_at,
            )
            return

        raise PlatformAPIError(
            status_code=401,
            code="BOT_INVITE_INVALID",
            message="Invite code is invalid, expired, or already used.",
            request_id=request_id,
        )

    def _allow_invite_request(self, source_ip: str) -> bool:
        now_epoch = datetime.now(tz=UTC).timestamp()
        timestamps = self._invite_rate_limit_index.setdefault(source_ip, [])
        window_start = now_epoch - float(self._invite_window_seconds)
        timestamps[:] = [item for item in timestamps if item >= window_start]
        if len(timestamps) >= self._invite_rate_limit:
            return False
        timestamps.append(now_epoch)
        return True

    def _record_audit(
        self,
        *,
        event_type: Literal["register", "rotate", "revoke", "share", "accept"],
        request_id: str,
        tenant_id: str,
        owner_user_id: str,
        actor_type: str,
        actor_id: str,
        metadata: dict[str, Any],
    ) -> None:
        self._store.validation_identity_audit_events.append(
            ValidationIdentityAuditRecord(
                id=self._store.next_id("validation_identity_audit"),
                event_type=event_type,
                request_id=request_id,
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                actor_type=actor_type,
                actor_id=actor_id,
                metadata=metadata,
            )
        )

    def _find_share_invite(
        self,
        *,
        invite_id: str,
    ) -> tuple[str, int, SharedValidationInviteRecord] | None:
        for run_id, invites in self._share_invites_by_run.items():
            for index, invite in enumerate(invites):
                if invite.invite_id == invite_id:
                    return run_id, index, invite
        return None

    def _recalculate_run_grants_for_user(self, *, run_id: str, user_id: str) -> None:
        permission: SharePermission | None = None
        for invite in self._share_invites_by_run.get(run_id, []):
            if invite.status != "accepted":
                continue
            if invite.accepted_user_id != user_id:
                continue
            permission = _max_permission(permission, invite.permission)

        grants = self._share_grants_by_run.get(run_id)
        if grants is None:
            return
        if permission is None:
            grants.pop(user_id, None)
        else:
            grants[user_id] = permission
        if not grants:
            self._share_grants_by_run.pop(run_id, None)


def _hash_secret(*, secret: str, salt: str) -> str:
    try:
        salt_bytes = bytes.fromhex(salt)
    except ValueError:
        salt_bytes = salt.encode("utf-8")
    digest = pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt_bytes,
        ValidationIdentityService._SECRET_HASH_ITERATIONS,
        dklen=ValidationIdentityService._SECRET_HASH_BYTES,
    )
    return digest.hex()


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("Invite email must be a valid address.")
    return normalized


def normalize_email(value: str) -> str:
    return _normalize_email(value)


def _normalize_bot_id(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "":
        raise ValueError("botId must be non-empty")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    if any(char not in allowed for char in normalized):
        raise ValueError("botId must contain only lowercase letters, numbers, and '-'.")
    return normalized


def _load_partner_credentials() -> dict[str, str]:
    raw_json = os.getenv("PLATFORM_BOT_PARTNER_CREDENTIALS_JSON", "{}")
    try:
        raw = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.warning("PLATFORM_BOT_PARTNER_CREDENTIALS_JSON is invalid JSON; ignoring value.")
        return {}
    if not isinstance(raw, dict):
        logger.warning("PLATFORM_BOT_PARTNER_CREDENTIALS_JSON must be a JSON object; ignoring invalid value.")
        return {}
    parsed: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        normalized_key = key.strip()
        normalized_value = value.strip()
        if normalized_key and normalized_value:
            parsed[normalized_key] = normalized_value
    return parsed


def _max_permission(current: SharePermission | None, new: SharePermission) -> SharePermission:
    if current == "review" or new == "review":
        return "review"
    return "view"


def _parse_utc_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if normalized == "":
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _resolve_share_invite_expiration(*, expires_at: str | None, request_id: str) -> str:
    now = datetime.now(tz=UTC)
    normalized = (expires_at or "").strip()
    if normalized == "":
        return _to_utc(now + timedelta(days=7))

    parsed = _parse_utc_datetime(normalized)
    if parsed is None:
        raise PlatformAPIError(
            status_code=400,
            code="VALIDATION_SHARE_INVALID",
            message="expiresAt must be an ISO8601 timestamp when provided.",
            request_id=request_id,
            details={"expiresAt": expires_at},
        )
    if parsed <= now:
        raise PlatformAPIError(
            status_code=400,
            code="VALIDATION_SHARE_INVALID",
            message="expiresAt must be in the future.",
            request_id=request_id,
            details={"expiresAt": expires_at},
        )
    return _to_utc(parsed)


def _invite_expired(expires_at: str | None) -> bool:
    if expires_at is None:
        return False
    expires_dt = _parse_utc_datetime(expires_at)
    if expires_dt is None:
        return True
    return datetime.now(tz=UTC) >= expires_dt


def _to_utc(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "ActorType",
    "BotRegistrationResult",
    "RegistrationMethod",
    "RuntimeActorIdentity",
    "SharePermission",
    "SharedValidationInviteRecord",
    "ValidationIdentityService",
    "normalize_email",
]

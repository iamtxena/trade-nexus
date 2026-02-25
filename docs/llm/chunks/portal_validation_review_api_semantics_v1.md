# Validation Review API Contracts And Response Semantics

Source: `docs/portal/api/validation-review-api-semantics.md`
Topic: `api`
Stable ID: `portal_validation_review_api_semantics_v1`

# Validation Review API Contracts And Response Semantics

## Canonical Contract Source

Validation review APIs are defined in `/docs/architecture/specs/platform-api.openapi.yaml` under the `Validation` tag.

## Endpoint Matrix

| Route | OperationId | Success Code | Semantics |
| --- | --- | --- | --- |
| `POST /v2/validation-runs` | `createValidationRunV2` | `202` | Starts a validation run and returns queued/accepted run metadata. |
| `GET /v2/validation-runs/{runId}` | `getValidationRunV2` | `200` | Returns run status (`queued`, `running`, `completed`, `failed`) and final decision state. |
| `GET /v2/validation-runs/{runId}/artifact` | `getValidationRunArtifactV2` | `200` | Returns canonical artifact payload (`validation_run` or compact snapshot). |
| `POST /v2/validation-runs/{runId}/review` | `submitValidationRunReviewV2` | `202` | Accepts trader/agent review decision for the run. |
| `POST /v2/validation-runs/{runId}/render` | `createValidationRunRenderV2` | `202` | Queues optional HTML/PDF render generation from canonical JSON. |
| `POST /v2/validation-bots/registrations/invite-code` | `registerValidationBotInviteCodeV2` | `201` | Self-registers a user-owned bot through invite-code trial flow (rate-limited). |
| `POST /v2/validation-bots/registrations/partner-bootstrap` | `registerValidationBotPartnerBootstrapV2` | `201` | Self-registers a user-owned bot through partner key/secret bootstrap flow. |
| `POST /v2/validation-bots/{botId}/keys/rotate` | `rotateValidationBotKeyV2` | `201` | Rotates bot key and returns a newly issued raw key once. |
| `POST /v2/validation-bots/{botId}/keys/{keyId}/revoke` | `revokeValidationBotKeyV2` | `200` | Revokes a bot key metadata record without exposing raw key. |
| `GET /v2/validation-sharing/runs/{runId}/invites` | `listValidationRunInvitesV2` | `200` | Lists email invites for one run scope only. |
| `POST /v2/validation-sharing/runs/{runId}/invites` | `createValidationRunInviteV2` | `201` | Creates a run-level invite by email. |
| `POST /v2/validation-sharing/invites/{inviteId}/revoke` | `revokeValidationInviteV2` | `200` | Revokes an existing invite. |
| `POST /v2/validation-sharing/invites/{inviteId}/accept` | `acceptValidationInviteOnLoginV2` | `200` | Accepts invite and grants run-level share in Shared Validation flow. |
| `POST /v2/validation-baselines` | `createValidationBaselineV2` | `201` | Promotes an existing run as baseline for replay/regression checks. |
| `POST /v2/validation-regressions/replay` | `replayValidationRegressionV2` | `202` | Compares baseline vs candidate run and returns merge/release gate decisions. |

## Canonical Artifact Semantics

1. `validation_run` JSON is authoritative for merge/release and audit.
2. `validation_llm_snapshot` is a compact derivative for agent analysis.
3. Render artifacts (`html`, `pdf`) are derived and must not replace canonical JSON records.
4. `finalDecision` uses contract enum values: `pass`, `conditional_pass`, `fail`.

## Bot Onboarding Paths

1. Invite-code trial path:
   - route: `POST /v2/validation-bots/registrations/invite-code`
   - request schema: `CreateBotInviteRegistrationRequest`
   - required fields: `inviteCode`, `botName`
   - includes `429` response for rate-limit enforcement
2. Partner bootstrap path:
   - route: `POST /v2/validation-bots/registrations/partner-bootstrap`
   - request schema: `CreateBotPartnerBootstrapRequest`
   - required fields: `partnerKey`, `partnerSecret`, `ownerEmail`, `botName`
3. Both paths return `BotRegistrationResponse` with:
   - `bot` metadata (`ownerUserId`, `registrationPath`)
   - `registration` audit metadata
   - `issuedKey` (including show-once `rawKey`)

## Key Lifecycle Semantics

1. Create:
   - initial bot registration response includes `issuedKey.rawKey` and `issuedKey.key`.
2. Show once:
   - `BotIssuedApiKey.rawKey` is explicitly one-time return only.
   - `BotKeyMetadata` never exposes `rawKey`.
3. Rotate:
   - route: `POST /v2/validation-bots/{botId}/keys/rotate`
   - returns fresh `issuedKey.rawKey` + `key` metadata.
4. Revoke:
   - route: `POST /v2/validation-bots/{botId}/keys/{keyId}/revoke`
   - returns `BotKeyMetadataResponse` with `status=revoked` and `revokedAt`.

## Actor Linkage Model

1. Actor type is explicit via `ValidationActorType` enum: `user | bot`.
2. `ValidationRun.actor` uses `ValidationRunActorMetadata` (`actorType`, `actorId`, optional `userId`, optional `botId`, `metadata`).
3. `ValidationInvite.invitedByActorType` uses same actor enum.
4. Bots are user-owned (`Bot.ownerUserId`), and v2 has no brand model (`brand`/`brandId` absent by contract).

## Run-Level Sharing Semantics

1. Sharing scope is run-level only:
   - all shared routes (invite lifecycle + shared review writes) are under `/v2/validation-sharing/...`.
2. Permission model is canonicalized to `ValidationSharePermission = view | review`:
   - `view` is read-only shared access.
   - `review` permits shared review writes through `POST /v2/validation-sharing/runs/{runId}/review`.
3. Backward compatibility:
   - legacy permission aliases (`comment`, `decide`) normalize to `review`.
4. Invite targeting is email-only:
   - `CreateValidationInviteRequest` requires `email` and does not include `userId`.
5. Invite lifecycle states:
   - `pending`, `accepted`, `revoked`, `expired`.
6. Granted share lifecycle states:
   - `active`, `revoked` (`ValidationRunShare`).
7. Invite acceptance:
   - `AcceptValidationInviteRequest` requires `acceptedEmail`.
   - response includes both updated `invite` and created/updated `share`.

## Review Decision Semantics

1. `reviewerType` is constrained to `agent` or `trader`.
2. `decision` is constrained to `pass`, `conditional_pass`, or `fail`.
3. `findings` are structured entries with `priority`, `confidence`, `summary`, and `evidenceRefs`.
4. Trader review is policy-controlled (`requireTraderReview`) and optional by profile.

## Identity, Auth, and Request Correlation

1. Global API auth uses bearer token or API key per OpenAPI security schemes.
2. Bot self-registration routes declare `security: []` and rely on invite-code or partner credentials in request payload/body.
3. Clients must not call provider services directly; integration flows stay on Platform API routes.
4. User/tenant scope must be derived from authenticated session context, not caller-provided identity headers.
5. `X-Request-Id` is used for trace correlation across web proxy and Platform API.
6. `Idempotency-Key` should be supplied for write calls (`POST`) to avoid duplicate effects.

## Error and Retry Semantics

1. `400` indicates invalid payload or policy shape.
2. `401` indicates missing/invalid auth context.
3. `404` indicates unknown run/baseline resource.
4. `409` indicates conflict (`duplicate pending invite`, `already-revoked`, or other state conflict cases).
5. `429` is used by invite-code registration path for rate limiting.
6. Retrying write calls should reuse the same `Idempotency-Key` only when payload is unchanged.

## Governance Checks

Run these checks for contract and docs alignment:

```bash
npx --yes --package=@redocly/cli@1.34.5 redocly lint docs/architecture/specs/platform-api.openapi.yaml
pytest backend/tests/contracts/test_openapi_contract_v2_validation_freeze.py
pytest backend/tests/contracts/test_platform_api_v2_handlers.py
npm --prefix docs/portal-site run ci
```

## Traceability

- Child issue: [#313](https://github.com/iamtxena/trade-nexus/issues/313)
- Parent issue: [#310](https://github.com/iamtxena/trade-nexus/issues/310)
- Validation web proxy auth: `/frontend/src/lib/validation/server/auth.ts`
- Validation web proxy transport: `/frontend/src/lib/validation/server/platform-api.ts`
- Contract governance: `/.github/workflows/contracts-governance.yml`
- Docs governance: `/.github/workflows/docs-governance.yml`

# API Contract Governance

## Objective

Guarantee that multiple teams can ship in parallel without integration breakage.

## Canonical Source

The single source of truth for public API contracts is:

- `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/specs/platform-api.openapi.yaml`

No public endpoint is considered valid unless represented in this file.

## Contract Lifecycle

1. Propose change via architecture/API issue.
2. Update OpenAPI spec first.
3. Generate SDK + mocks from updated spec.
4. Implement backend changes.
5. Run contract tests.
6. Merge only when spec, generated artifacts, and implementation are aligned.

## Required Issue Templates

Use structured templates for governance proposals:

1. Architecture changes:
   - `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/.github/ISSUE_TEMPLATE/architecture_change.yml`
2. API contract changes:
   - `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/.github/ISSUE_TEMPLATE/api_contract_change.yml`

For breaking proposals, the issue must include an explicit architecture approval comment URL before merge.

## Versioning Rules

1. URL versioning is mandatory (`/v1`, `/v2`, ...).
2. Breaking changes require a new major API version.
3. Additive changes are allowed within the same version.
4. Deprecated fields/endpoints must include a removal date.

## Breaking Change Definition

Any of the following is breaking:

- removing or renaming endpoint/field,
- changing field type,
- making optional field required,
- changing enum behavior incompatibly,
- changing auth requirements.

## Gate1 Freeze Policy

Gate1 is a strict contract freeze for the v1 path set and operation signatures.

1. No endpoint additions, removals, or repurposing under `/v1`.
2. No incompatible request/response shape changes under `/v1`.
3. SDK/mocks/CI gates must pass for every contract-related PR.
4. Breaking proposals are blocked during Gate1 unless architecture approval is explicitly documented.

### Gate1 Exception Path (breaking proposal)

All of the following are required before a breaking proposal can proceed:

1. Open issue using the API contract template with impact, migration, and rollback notes.
2. Architecture approval comment URL from `@iamtxena`.
3. Explicit versioning plan (new major version path, e.g. `/v2`).
4. Linked CI evidence proving the change was intentionally reviewed.

## Required Contract Conventions

### 1) Error envelope

All non-2xx responses follow:

```json
{
  "error": {
    "code": "STRING_CODE",
    "message": "Human readable summary",
    "details": {}
  },
  "requestId": "uuid"
}
```

### 2) Idempotency

Required headers for side-effecting writes:

- `Idempotency-Key` on:
  - `POST /v1/orders`
  - `POST /v1/deployments`

Behavior:

- same key + same payload: return original success result,
- same key + different payload: return `409`.

### 3) Request tracing

`X-Request-Id` accepted from caller and propagated to downstream systems.

### 4) Pagination

All list endpoints must use a shared pagination shape:

```json
{
  "items": [],
  "nextCursor": "opaque-or-null"
}
```

### 5) Async operation lifecycle

Long operations return resources with status:

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

## SDK Policy

1. Generate and publish a typed SDK from OpenAPI.
2. Clients (CLI, web, agents) must use SDK, not hand-written HTTP calls.
3. Generated SDK version must match API version support matrix.

## Testing Policy

### Contract tests

- validate every implemented route against OpenAPI schema,
- validate error envelopes and status codes,
- validate idempotency behavior.

### Gate5 Contract Matrix (minimum CI gate)

The `contracts-governance` GitHub workflow is the required status check for contract-facing PRs and must run:

1. `pytest backend/tests/contracts/test_openapi_contract_baseline.py`
2. `pytest backend/tests/contracts/test_openapi_contract_freeze.py`
3. `pytest backend/tests/contracts --ignore=backend/tests/contracts/test_openapi_contract_baseline.py --ignore=backend/tests/contracts/test_openapi_contract_freeze.py`
4. `bash contracts/scripts/verify-sdk-drift.sh`
5. `bash contracts/scripts/mock-smoke-test.sh`
6. `bash contracts/scripts/check-breaking-changes.sh`

This matrix enforces both OpenAPI governance and runtime contract behavior (v1/v2 handlers, risk, orchestrator, adapters, and client lane tests).

### Consumer tests

- CLI tests use generated mock server responses,
- no direct dependency on provider-specific APIs.

## Ownership

- Platform API team owns OpenAPI schema.
- Each tag/endpoint group has a DRI.
- Architecture owner approves breaking changes.

## Migration Policy for Existing Prototypes

1. Existing prototype endpoints can remain temporarily.
2. They must be marked `legacy` and not used by new clients.
3. New client work must target OpenAPI-defined routes only.
4. Legacy endpoint removals require migration notes in changelog.

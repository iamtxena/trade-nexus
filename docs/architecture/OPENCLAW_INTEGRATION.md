# OpenClaw Integration (Gate4 OC-01)

## Purpose

Define OpenClaw as a first-class **client lane** in Trade Nexus v2.

This document is normative for client boundary behavior and must remain consistent with:

1. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/TARGET_ARCHITECTURE_V2.md`
2. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/INTERFACES.md`
3. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/specs/platform-api.openapi.yaml`

If there is any conflict, OpenAPI and `INTERFACES.md` win.

## OpenClaw Lane Definition

OpenClaw is an external conversational client surface, equivalent in boundary status to Web and CLI.

OpenClaw responsibilities:

- gather user intent and context,
- call Trade Nexus public API operations through approved client interfaces,
- render responses and notifications back to the user.

OpenClaw non-responsibilities:

- calling provider APIs,
- owning platform orchestration state,
- introducing undocumented backend endpoints.

## Non-Negotiable Boundary Rules

1. OpenClaw remains a **client lane only**.
2. OpenClaw must call Trade Nexus through Platform API contracts (direct SDK/API or CLI wrapper).
3. OpenClaw must not call Lona, live-engine, or data providers directly.
4. Provider integrations are only allowed inside platform adapters.
5. OpenClaw behavior changes that need new backend routes require OpenAPI-first updates.

## Allowed Integration Patterns

### Pattern A: SDK/API-first OpenClaw Client

OpenClaw skill -> Trade Nexus SDK/generated client -> Platform API -> platform adapters -> providers

Use when the OpenClaw runtime can use stable HTTP SDK calls directly.

### Pattern B: CLI-mediated OpenClaw Client

OpenClaw skill -> `trading-cli` -> Platform API -> platform adapters -> providers

Use when CLI policy, local wrappers, or runtime constraints make CLI mediation preferable.

Both patterns are valid as long as boundary rules are enforced.

## Identity and Request Correlation

OpenClaw requests must preserve platform identity/correlation inputs:

- authentication via `Authorization` bearer token or `X-API-Key`,
- caller correlation via `X-Request-Id` when available,
- idempotency keys on side-effecting writes where required by OpenAPI.

OpenClaw must not synthesize provider-facing identity headers.

## Contract Scope in OC-01

OC-01 does **not** add OpenClaw-specific backend endpoints.

OC-01 confirms that OpenClaw uses the existing public surface and that all OpenClaw-facing behavior is constrained by canonical contracts.

Conversation-specific API additions are handled separately in CONV-01 under additive `/v2` routes.

## OC-02 Client Integration Reference

Gate4 OC-02 introduces a concrete OpenClaw client integration module that consumes Platform API routes only:

- `/backend/src/platform_api/clients/openclaw_client.py`

Integration guarantees:

1. Uses only documented `/v1/*` and `/v2/*` routes.
2. Sets `channel=openclaw` for conversation session initialization.
3. Preserves auth, tenant/user identity, request correlation, and idempotency headers.
4. Does not include or require provider-direct HTTP calls.

Contract verification:

- `/backend/tests/contracts/test_openclaw_client_integration.py`
- `/backend/tests/contracts/test_openclaw_e2e_flow.py`

## Capability Matrix (Client-Lane View)

| Capability | OpenClaw Allowed | Required Contract |
| --- | --- | --- |
| Market scan | Yes | `/v1/research/market-scan` |
| Strategy lifecycle | Yes | `/v1/strategies*` |
| Backtests | Yes | `/v1/strategies/{strategyId}/backtests`, `/v1/backtests/{backtestId}` |
| Deployments | Yes | `/v1/deployments*` |
| Orders | Yes | `/v1/orders*` |
| Portfolio views | Yes | `/v1/portfolios*` |
| Dataset flow | Yes | `/v1/datasets*` |
| Provider direct calls | No | Forbidden by architecture boundary |

## Failure and Fallback Contract

If OpenClaw-side wrappers fail:

1. return the platform error envelope details to user-facing logs/UI,
2. preserve `requestId` for triage,
3. do not bypass Platform API for fallback execution.

## Operational Checklist (OC-01 Exit)

1. OpenClaw lane boundaries are documented in architecture and portal docs.
2. Contract guard test enforces "client lane only" and "no provider direct integration" statements.
3. Parent issue status updates include links to implementation evidence.
4. No undocumented endpoints are introduced.

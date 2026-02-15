---
title: Gate4 Conversation Contract
summary: Contract-defined conversation API semantics across CLI, Web, and OpenClaw client lanes, including context-memory behavior.
owners:
  - Team E
  - Team B
  - Team G
updated: 2026-02-14
---

# Gate4 Conversation Contract

## Objective

Define one conversation contract shared by CLI, Web, and OpenClaw, with additive `/v2` API semantics.

## Endpoints

- `POST /v2/conversations/sessions`
- `GET /v2/conversations/sessions/{sessionId}`
- `POST /v2/conversations/sessions/{sessionId}/turns`

## Core Semantics

1. Session creation requires explicit `channel` value.
2. Channel enum is normalized: `cli | web | openclaw`.
3. Turn creation appends immutable turn records and updates session timestamps.
4. Missing session IDs return canonical `ErrorResponse` with `404`.
5. Conversation contract is additive under `/v2`; `/v1` remains unchanged.

## Context Memory Semantics (CONV-02)

1. Memory is scoped per `tenant_id:user_id` and reused across that user's conversation sessions.
2. Each turn updates bounded context memory:
  - recent messages (bounded by retention policy),
  - inferred intent (`deploy | backtest | order | risk | portfolio`),
  - linked trading artifacts (`strat-*`, `dep-*`, `ord-*`, `portfolio-*`, `bt-*`, `dataset-*`),
  - symbol references (for example `BTCUSDT`).
3. Session metadata exposes current memory under `contextMemory`.
4. Turn metadata includes `contextMemorySnapshot` so clients can render deterministic multi-turn context.
5. Memory is isolated by user identity and does not leak across users.

## Boundary Alignment

- Conversation is a public contract concern, not a provider integration.
- Conversation routes remain inside Platform API.
- Provider boundaries are unchanged: adapter-only integrations.

## Traceability

- OpenAPI: `/docs/architecture/specs/platform-api.openapi.yaml`
- Interface definition: `/docs/architecture/INTERFACES.md`
- Parent epics: `#80`, `#106`, `#81`
- Gate4 docs issue: `#137`

---
title: Gate4 OpenClaw Client Lane
summary: Contract-defined OpenClaw client-lane boundaries and integration constraints for Gate4 OC-01.
owners:
  - Team E
  - Team G
updated: 2026-02-14
---

# Gate4 OpenClaw Client Lane

## Objective

Define OpenClaw as a first-class client lane without changing provider boundaries.

## Boundary Contract

1. OpenClaw is a client lane only.
2. OpenClaw calls Platform API contracts only.
3. OpenClaw must never call provider APIs directly.
4. Provider integrations remain adapter-only inside `trade-nexus` backend.
5. OpenClaw-specific backend behavior must be contract-first in OpenAPI.

## Allowed Call Paths

- OpenClaw skill -> SDK/API client -> Platform API
- OpenClaw skill -> `trading-cli` -> Platform API

Both paths are valid if they preserve auth, request correlation, and idempotency semantics defined in OpenAPI.

## Explicitly Forbidden

- OpenClaw -> Lona API direct calls
- OpenClaw -> live-engine direct calls
- OpenClaw -> data provider direct calls
- Introducing undocumented `/v1/openclaw/*` endpoints

## Traceability

- Architecture contract: `/docs/architecture/OPENCLAW_INTEGRATION.md`
- Interface boundary: `/docs/architecture/INTERFACES.md`
- Public API source: `/docs/architecture/specs/platform-api.openapi.yaml`
- Parent epics: `#80`, `#106`, `#81`
- Gate4 docs issue: `#137`

---
title: Platform API Contract
summary: Integration entrypoint and contract rules for Platform API consumers.
owners:
  - Gate1 Docs Team
updated: 2026-02-14
---

# Platform API Contract

## Canonical Contract Source

- `/docs/architecture/specs/platform-api.openapi.yaml`

All public API behavior, request/response schemas, and examples are governed by this file.

## Consumer Rules

1. Integrations must use generated SDK artifacts where available.
2. Endpoint usage must map to OpenAPI-defined `operationId`s.
3. Breaking changes require architecture approval and major-version strategy.

## Supporting Docs

- `/docs/architecture/INTERFACES.md`
- `/docs/architecture/API_CONTRACT_GOVERNANCE.md`
- `/docs/architecture/specs/SDK_RELEASE.md`
- `/docs/architecture/specs/MOCK_SERVER.md`

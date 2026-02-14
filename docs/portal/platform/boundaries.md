---
title: Platform Boundaries
summary: Non-negotiable architecture boundaries for platform, clients, and provider adapters.
owners:
  - Gate1 Docs Team
updated: 2026-02-14
---

# Platform Boundaries

## Boundary Rules

1. Client applications consume Platform API only.
2. Client applications do not call provider APIs directly.
3. Provider API calls are isolated to adapter implementations.
4. Public endpoint changes must be represented in OpenAPI first.
5. Contract and governance checks must pass before merge.

## Contract Files

- `/docs/architecture/specs/platform-api.openapi.yaml`
- `/docs/architecture/API_CONTRACT_GOVERNANCE.md`
- `/docs/architecture/INTERFACES.md`

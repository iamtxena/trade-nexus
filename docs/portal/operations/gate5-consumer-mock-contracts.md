---
title: Gate5 Consumer-Driven Mock Contract Checks
summary: CI-enforced consumer contract assertions against the generated Platform API mock server.
owners:
  - Team F
  - Team E
updated: 2026-02-16
---

# Gate5 Consumer-Driven Mock Contract Checks

## Objective

Ensure client-facing payload contracts remain compatible before release by validating generated mock responses from the authoritative Platform API OpenAPI spec.

## CI Gates

`contracts-governance` must run both:

1. `bash contracts/scripts/mock-smoke-test.sh`
2. `bash contracts/scripts/mock-consumer-contract-test.sh`

## Consumer Scope

Current consumer-driven assertions include:

1. Trading CLI lane expectations on `/v1/research/market-scan` and `/v1/strategies`.
2. OpenClaw lane expectations on `/v2/conversations/sessions` and `/v2/conversations/sessions/{sessionId}/turns`.

## Failure Semantics

Merge is blocked when either check fails for any of:

1. route/routing breakage,
2. missing required client envelope fields,
3. non-conforming session/turn shape for OpenClaw lane flows.

## Traceability

- `contracts/scripts/mock-smoke-test.sh`
- `contracts/scripts/mock-consumer-contract-test.sh`
- `.github/workflows/contracts-governance.yml`
- `docs/architecture/INTERFACES.md`

---
title: Gate3 Execution Hardening
summary: Execution adapter hardening, lifecycle transition mapping, and reconciliation/drift operations.
owners:
  - Gate3 Docs Team
updated: 2026-02-14
---

# Gate3 Execution Hardening

## Scope

Gate3 execution hardening covers:

1. `ExecutionAdapter` backed by live-engine internal service routes.
2. Canonical deployment lifecycle transition mapping.
3. Deployment/order reconciliation and drift checks.

## Lifecycle Mapping

Platform lifecycle states:

- `queued`
- `running`
- `paused`
- `stopping`
- `stopped`
- `failed`

Provider states are normalized before platform persistence. Unknown provider states are treated as `failed`.

## Reconciliation Flow

1. Platform loads current deployment/order state.
2. Adapter fetches provider state from live-engine internal routes.
3. Reconciliation service computes drift and transition validity.
4. Platform updates resource state and records drift events.

## Operator Guidance

Drift event payloads include:

- `resource_type`
- `resource_id`
- `provider_ref_id`
- `previous_state`
- `provider_state`
- `resolution`

Use these events to audit status corrections and detect recurring provider mismatches.

## Post-GateX R1 Remediation

- `#207`: list adapter paths (`deployments`, `orders`, `portfolios`) now forward caller `tenant_id` and `user_id`.
- Runtime services do not inject fallback tenant/user identities for provider list requests.

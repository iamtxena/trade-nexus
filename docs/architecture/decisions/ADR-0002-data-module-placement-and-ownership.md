# ADR-0002: Data Module Placement and Ownership

- Status: Accepted
- Date: 2026-02-13
- Issue: [#67](https://github.com/iamtxena/trade-nexus/issues/67)

## Context

Trade Nexus v2 needs a clear boundary for data/knowledge capabilities so teams can
deliver in parallel without leaking provider-specific integrations into clients.

## Decision

1. Place the Data Module in a separate repository: `iamtxena/trader-data`.
2. Keep external client access routed through Platform API in `trade-nexus`.
3. Keep provider-specific API interactions inside adapter implementations.

## Ownership Model

1. Data lead owns `trader-data` backlog and module delivery.
2. Architecture/Contracts lead owns boundary alignment with OpenAPI governance.
3. Client lead owns SDK-only client integrations and prevents direct provider calls.

## Alternatives Considered

1. Keep Data Module inside `trade-nexus`.
2. Place Data Module in Lona-owned surface.
3. Create separate `trader-data` repo with adapter-first boundary.

## Rationale

1. Independent lifecycle for high-change data ingestion and storage concerns.
2. Cleaner ownership boundaries for Gate1 and beyond.
3. Preserves Platform API as the single public contract for clients.

## Consequences

1. Cross-repo coordination is required for contract-impacting data changes.
2. `trader-data` may evolve internal adapters independently of client releases.
3. Gate1 work must document data capability exposure through Platform API only.

## Gate1 Handoff DRI Roles

1. Architecture/Contracts lead: approve contract-impacting data boundaries.
2. Client lead: consume data capabilities through generated SDK only.
3. Data lead: deliver ingestion, normalization, and knowledge context capabilities.

## Rollback Trigger

Revisit this decision if repository split causes sustained delivery slowdown or if
critical data changes repeatedly require synchronized monorepo-level releases.

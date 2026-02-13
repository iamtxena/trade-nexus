# ADR-0001: Contracts Repository Location for Gate0

- Status: Accepted
- Date: 2026-02-13
- Issue: [#17](https://github.com/iamtxena/trade-nexus/issues/17)

## Context

Trade Nexus v2 requires a single canonical contract source with governance gates.
Gate0 must unblock parallel delivery quickly while keeping API scope frozen.

## Decision

For Gate0, keep the canonical contract source in `trade-nexus` at:

- `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/specs/platform-api.openapi.yaml`

Add contract-governance CI and baseline contract behavior tests in `trade-nexus`.
Defer splitting to `trade-nexus-contracts` until a later gate if operational pressure justifies it.

## Alternatives Considered

1. Create `trade-nexus-contracts` immediately in Gate0.
2. Keep contracts in `trade-nexus` for Gate0 and harden governance first.

## Rationale

1. Fastest path to enforce governance without introducing repo migration risk.
2. Preserves one authoritative OpenAPI source while Team A prepares Gate1 freeze tasks.
3. Avoids dual-source drift during bootstrap of `trading-cli` and `trader-data`.

## Consequences

1. Team A owns contract lifecycle in `trade-nexus` during Gate0/Gate1.
2. Gate1 workstreams consume artifacts from the in-repo OpenAPI source.
3. A future split remains possible, but only after parity gates are proven.

## Rollback Trigger

Re-open the repo-split decision if either condition is met:

1. Contract governance changes create repeated cross-team merge conflicts that block delivery.
2. SDK/mock publication cadence requires independent release lifecycle from platform code.

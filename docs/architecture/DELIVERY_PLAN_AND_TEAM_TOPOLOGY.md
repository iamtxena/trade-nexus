# Delivery Plan and Team Topology

## Goal

Turn the v2 target architecture into a multi-team execution program where teams can work independently with minimal coordination overhead.

This plan assumes:

1. Lona stays fixed as external architecture.
2. Platform API is the only public backend contract.
3. CLI is external and consumes Platform API only.

## Operating Model

### Master Architect (you + architect role)

Responsibilities:

- approve contract changes,
- resolve cross-team design conflicts,
- enforce architecture gates,
- maintain dependency roadmap.

### Independent Delivery Teams

- Team A: Contracts and SDK
- Team B: Platform Core (API + orchestration)
- Team C: Lona/Strategy Integration
- Team D: Execution Integration (live-engine + adapter)
- Team E: CLI Product
- Team F: Platform Reliability (observability + release gates)

## Repository Topology

### Existing Repos

1. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus` (platform source)
2. `/Users/txena/sandbox/16.enjoy/trading/live-engine` (execution runtime source)

### New Repos to Create

1. `trading-cli` (required)
   - purpose: public CLI client only
   - allowed dependencies: generated Platform SDK only
   - forbidden: direct Lona/live-engine HTTP calls

2. `trade-nexus-contracts` (recommended)
   - purpose: OpenAPI, generated SDK, mock server, contract CI
   - benefit: isolates contract ownership so all teams consume one independent artifact

3. `trade-nexus-runbooks` (optional)
   - purpose: operating procedures, on-call playbooks, cutover guides
   - use when team scale increases

## Repo Creation Ticket Sector

These tickets should be created first.

| Ticket | Repo | Owner Team | Description | Done When |
|-------|------|------------|-------------|-----------|
| REPO-01 | trade-nexus | Team A | Bootstrap `trade-nexus-contracts` repository (or formally decide to keep contracts in `trade-nexus`) | Decision recorded and CI scaffold committed |
| REPO-02 | trade-nexus | Team E | Create `trading-cli` repository with release pipeline | Repo created, default branch protected, first CLI bootstrap merged |
| REPO-03 | trade-nexus | Team A | Add SDK publishing workflow (npm package) | SDK package published from contract source |
| REPO-04 | trade-nexus | Team F | Add organization-level issue templates for architecture/contract changes | Templates available and referenced in docs |

## Program Workstreams and Ticket Sectors

## Sector C: Contract and SDK (Team A)

Source of truth:

- `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/specs/platform-api.openapi.yaml`

Tickets:

| Ticket | Repo | Dependencies | Description |
|-------|------|--------------|-------------|
| C-01 | trade-nexus-contracts (or trade-nexus) | REPO-01 | Finalize OpenAPI v1 endpoints for strategy, backtest, deployments, portfolios, orders |
| C-02 | trade-nexus-contracts (or trade-nexus) | C-01 | Generate TypeScript SDK and pin semantic versioning policy |
| C-03 | trade-nexus-contracts (or trade-nexus) | C-01 | Generate mock server for consumer tests |
| C-04 | trade-nexus-contracts (or trade-nexus) | C-02/C-03 | Add CI gates: spec lint, breaking-change detection, SDK generation check |

## Sector P: Platform Core (Team B)

Tickets:

| Ticket | Repo | Dependencies | Description |
|-------|------|--------------|-------------|
| P-01 | trade-nexus | C-01 | Implement API handlers exactly matching OpenAPI contract |
| P-02 | trade-nexus | C-01 | Add standardized error envelope and request-id propagation |
| P-03 | trade-nexus | C-01 | Add idempotency-key enforcement for `POST /v1/orders` and `POST /v1/deployments` |
| P-04 | trade-nexus | P-01 | Implement async resource status model (`queued/running/completed/failed/cancelled`) |
| P-05 | trade-nexus | P-01 | Add cursor pagination helpers across list endpoints |

## Sector L: Lona Integration (Team C)

Tickets:

| Ticket | Repo | Dependencies | Description |
|-------|------|--------------|-------------|
| L-01 | trade-nexus | C-01 | Create `LonaAdapter` interface and implementation |
| L-02 | trade-nexus | L-01 | Normalize strategy generation outputs to platform schema |
| L-03 | trade-nexus | L-01 | Normalize backtest lifecycle and metrics mapping |
| L-04 | trade-nexus | L-01 | Add resilience policy (timeouts, retries, typed provider errors) |

## Sector E: Execution Integration (Team D)

Tickets:

| Ticket | Repo | Dependencies | Description |
|-------|------|--------------|-------------|
| E-01 | trade-nexus | C-01 | Create `ExecutionAdapter` interface in platform |
| E-02 | trade-nexus + live-engine | E-01 | Build live-engine adapter implementation without leaking live-engine API shape |
| E-03 | live-engine | E-02 | Align trade schema/route semantics with adapter contract |
| E-04 | trade-nexus + live-engine | E-02 | Add deployment and order reconciliation flow |

## Sector CLI: External Client (Team E)

Tickets:

| Ticket | Repo | Dependencies | Description |
|-------|------|--------------|-------------|
| CLI-01 | trading-cli | REPO-02 + C-02 | Bootstrap command framework using generated SDK |
| CLI-02 | trading-cli | CLI-01 | Implement strategy + backtest commands |
| CLI-03 | trading-cli | CLI-01 | Implement deployment + portfolio + orders commands |
| CLI-04 | trading-cli | CLI-02/03 | Remove any direct provider calls and enforce SDK-only rule |

## Sector R: Reliability and Release (Team F)

Tickets:

| Ticket | Repo | Dependencies | Description |
|-------|------|--------------|-------------|
| R-01 | trade-nexus | P-02 | Structured logs with `tenant_id`, `user_id`, `request_id` |
| R-02 | trade-nexus | P-01 | Contract test suite against OpenAPI |
| R-03 | trade-nexus + trading-cli | C-03 + CLI-01 | Consumer-driven tests using mock server |
| R-04 | trade-nexus | R-01 | SLOs and alerting for latency/error budget |

## Agent-Specific Focus and Ticket Sectors

This addresses the request to focus each agent independently.

## Agent: Orchestrator

Scope: task routing, session state, sequencing, fallback policy.

Tickets:

| Ticket | Repo | Dependencies | Description |
|-------|------|--------------|-------------|
| AG-ORCH-01 | trade-nexus | P-01 | Define orchestrator state machine and transitions |
| AG-ORCH-02 | trade-nexus | AG-ORCH-01 | Implement priority queue and cancellation model |
| AG-ORCH-03 | trade-nexus | AG-ORCH-01 | Retry/failure policy with max budget per run |
| AG-ORCH-04 | trade-nexus | R-01 | Add execution traces per orchestrator run |

## Agent: Research

Scope: market scan, idea generation, signal packaging.

Tickets:

| Ticket | Repo | Dependencies | Description |
|-------|------|--------------|-------------|
| AG-RES-01 | trade-nexus | C-01 | Implement research endpoint + schema validation |
| AG-RES-02 | trade-nexus | L-01 | Integrate Lona strategy generation via adapter |
| AG-RES-03 | trade-nexus | AG-RES-01 | Add caching and freshness policy for market context |
| AG-RES-04 | trade-nexus | AG-RES-02 | Add cost controls and provider budget guardrails |

## Agent: Risk Manager

Scope: exposure limits, drawdown controls, pre-trade checks.

Tickets:

| Ticket | Repo | Dependencies | Description |
|-------|------|--------------|-------------|
| AG-RISK-01 | trade-nexus | P-01 | Define machine-readable risk policy schema |
| AG-RISK-02 | trade-nexus | AG-RISK-01 | Pre-trade risk evaluation before `orders` and `deployments` |
| AG-RISK-03 | trade-nexus | AG-RISK-01 | Kill-switch and max drawdown breach handling |
| AG-RISK-04 | trade-nexus | AG-RISK-02 | Risk decision audit trail for every blocked/approved action |

## Agent: Execution

Scope: deployment and trading actions through execution adapter.

Tickets:

| Ticket | Repo | Dependencies | Description |
|-------|------|--------------|-------------|
| AG-EXE-01 | trade-nexus | E-01 | Implement execution command layer using adapter only |
| AG-EXE-02 | trade-nexus + live-engine | E-02 | Map deployment lifecycle and status transitions |
| AG-EXE-03 | trade-nexus | P-03 | Enforce idempotency semantics in execution commands |
| AG-EXE-04 | trade-nexus + live-engine | E-04 | Add reconciliation checks for drift between platform and engine |

## Delegation Strategy (Who Starts What First)

### Week 1 (parallel kickoff)

- Team A: C-01/C-02/C-03
- Team B: P-01 design skeleton against spec draft
- Team C: L-01 interface design
- Team D: E-01 interface design
- Team E: REPO-02 + CLI-01 scaffold
- Team F: R-02 harness scaffold

### Week 2

- Team A closes C-04
- Teams B/C/D implement adapter-backed vertical slices
- Team E integrates generated SDK and starts feature commands
- Team F enables CI gates and trace logging baseline

### Week 3

- Agent-focused tickets (AG-*) distributed across Teams B/C/D
- end-to-end flow tests across strategy -> backtest -> deploy -> order -> portfolio

### Week 4

- hardening, deprecation of legacy prototype endpoints, release readiness

## Architecture Gates (must pass)

1. No external endpoint outside OpenAPI.
2. No CLI direct call to Lona/live-engine.
3. No adapter call without explicit tenant/user context.
4. No side-effecting write without idempotency policy.
5. No merge if contract and implementation diverge.

## Hand-off Package for Each Team

Each team receives:

1. Relevant section of this document.
2. API contract snapshot (OpenAPI version tag).
3. Definition of done for their ticket sector.
4. Named dependencies and unblock owner.

## What You Can Delegate Immediately

1. Team A can own contract lifecycle now.
2. Team E can start new CLI repo now.
3. Team D can open execution adapter integration tickets now.
4. Team B can implement API endpoints once C-01 is frozen.

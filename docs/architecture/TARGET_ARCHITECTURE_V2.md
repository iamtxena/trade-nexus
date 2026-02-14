# Trade Nexus Target Architecture v2

## Purpose

This is the proposed **to-be architecture** for Trade Nexus.

It is designed to:

- keep **Lona integration** as a fixed external dependency,
- make **Platform API** the only public backend contract,
- allow teams to work independently with contract-first development,
- keep execution engines replaceable (live-engine today, other engines later).

## Fixed Constraints

1. Lona remains external and is not re-architected.
2. CLI is a first-class interface and should live in an external repository.
3. Web and third-party agents must use the same Platform API contract.

## Architecture Principles

1. API-first: OpenAPI is the source of truth.
2. Replaceable adapters: provider-specific logic is behind internal interfaces.
3. Async by default for long-running operations (backtest, deploy).
4. Strong tenancy boundaries in every service call.
5. Idempotent write operations.
6. Explicit versioning (`/v1`) and backwards compatibility policy.

## System Context

```text
Clients
  - trading-cli (external repo)
  - Web UI
  - API consumers / agent clients
        |
        v
Trade Nexus Platform API (single public entrypoint)
  - AuthN/AuthZ
  - Request validation
  - Orchestration and domain services
        |
        +--> Lona Adapter (fixed dependency)
        |      - strategy generation
        |      - backtesting
        |
        +--> Execution Adapter
        |      - live-engine (current implementation)
        |      - future engines
        |
        +--> Data/Knowledge Adapter
               - market/news context
               - portfolio and analytics store
```

## Bounded Contexts

### 1) API Gateway + Contract Layer

Responsibilities:

- expose public REST contract,
- enforce schema, auth, idempotency, rate limits,
- map external DTOs to internal commands.

Ownership: Platform API team.

### 2) Strategy Lab

Responsibilities:

- research requests,
- strategy lifecycle (`draft -> tested -> deployable`),
- backtest orchestration via Lona.

Ownership: Strategy/AI team.

### 3) Execution Control

Responsibilities:

- deployment lifecycle (`pending -> running -> paused -> stopped -> failed`),
- trade/order operations,
- broker/paper execution via execution adapter.

Ownership: Execution team.

### 4) Portfolio and Risk

Responsibilities:

- portfolio snapshots,
- realized/unrealized PnL,
- risk limits and policy checks before execution.

Ownership: Risk/Portfolio team.

### 5) Market Context and Knowledge

Responsibilities:

- market/news context retrieval,
- normalized signals for research and strategy evaluation,
- cached query endpoints for clients,
- dataset lifecycle orchestration (upload/validate/transform/publish),
- lineage from raw artifacts to backtest-ready datasets.

Ownership: Data/Knowledge team.

## Public Interface Contract

Canonical file:

- `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/specs/platform-api.openapi.yaml`

Rule:

- If docs and code differ, the OpenAPI contract is authoritative.

## Internal Adapter Contracts

Each external dependency is wrapped behind an internal interface.

### Lona Adapter (fixed)

- `createStrategyFromDescription(...)`
- `runBacktest(...)`
- `getBacktestReport(...)`
- `listSymbols(...)`
- `downloadMarketData(...)`
- `publishDataset(...)` (connector path only, no Lona internal changes)

### Execution Adapter (replaceable)

- `createDeployment(...)`
- `stopDeployment(...)`
- `getDeployment(...)`
- `placeOrder(...)`
- `cancelOrder(...)`
- `getPortfolioSnapshot(...)`

### Data Adapter (source of truth for datasets)

- `initUpload(...)`
- `completeUpload(...)`
- `validateDataset(...)`
- `transformDataset(...)`
- `publishToLona(...)`
- `getDataset(...)`
- `listDatasets(...)`

This allows replacing live-engine without breaking API consumers.

## Data Ownership

1. Platform API owns canonical user-facing entities:
   - strategies
   - backtests (metadata/status)
   - deployments
   - orders
   - portfolio snapshots
2. External systems own execution internals and strategy runtime internals.
3. Platform persists provider references (`provider_ref_id`) but never leaks provider-specific shapes directly.

## Identity and Tenancy Model

1. External callers authenticate with bearer token or API key.
2. Platform resolves one canonical `tenant_id` and `user_id`.
3. Adapters receive explicit tenant/user context in headers/metadata.
4. No adapter may infer identity from local defaults.

## Operation Model

### Synchronous operations

- read portfolio
- list strategies
- get deployment status

### Asynchronous operations

- market scan/research
- backtest
- deployment start/stop

Async operations return resource IDs and status. Clients poll status endpoints.

## Observability and Reliability

Required cross-cutting controls:

1. `X-Request-Id` propagated end-to-end.
2. Structured logs with `tenant_id`, `user_id`, `resource_id`.
3. Timeouts/retries/circuit breakers in adapters.
4. Idempotency for `POST /orders` and `POST /deployments`.
5. Error envelope standardized in API contract.

## Repository Strategy

### trade-nexus (platform)

- Platform API
- domain services
- adapters
- contract tests
- OpenAPI source

### trading-cli (new external repo)

- generated SDK from OpenAPI
- CLI commands only
- no direct calls to Lona or execution engines

### live-engine (current adapter target)

- execution implementation behind Platform adapter
- can change freely as long as adapter contract is satisfied

## Delivery Phases

### Phase 1: Contract freeze

- finalize OpenAPI v1 for core workflows,
- generate SDK and mocks,
- stop introducing undocumented endpoints.

### Phase 2: Adapter hardening

- implement Lona adapter boundary,
- implement execution adapter boundary,
- add contract tests for both.

### Phase 3: Client decoupling

- move CLI to external repo,
- switch CLI to generated SDK,
- deprecate direct CLI -> Lona/live-engine calls.

### Phase 4: Scale and resilience

- async workers for long tasks,
- event stream/webhooks,
- multi-region and disaster recovery.

For detailed data-plane implementation and gate execution, see:

- `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/DATA_LIFECYCLE_AND_LONA_CONNECTOR_V2.md`
- `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/GATE_TEAM_EXECUTION_PLAYBOOK.md`

## Acceptance Criteria

1. Any team can develop using only OpenAPI + mocks.
2. Replacing execution engine does not require CLI or web changes.
3. A single request trace links API -> adapter -> provider logs.
4. No public endpoint bypasses Platform API boundary.

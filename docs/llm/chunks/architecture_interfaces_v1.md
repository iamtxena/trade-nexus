# Interface Definitions (v2)

Source: `docs/architecture/INTERFACES.md`
Topic: `architecture`
Stable ID: `architecture_interfaces_v1`

# Interface Definitions (v2)

This document defines the interface model for the to-be architecture.

## Canonical Sources

1. Public API contract: `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/specs/platform-api.openapi.yaml`
2. Governance rules: `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/API_CONTRACT_GOVERNANCE.md`
3. Architecture boundary decisions: `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/TARGET_ARCHITECTURE_V2.md`
4. Generated SDK source: `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/sdk/typescript` (package `@trade-nexus/sdk`)

If any previous endpoint list conflicts with the OpenAPI file, the OpenAPI file wins.

## Interface Layers

```text
External Clients
  -> Platform API (public, versioned)
    -> Domain Services (internal)
      -> Adapters (internal provider contracts)
        -> Lona / Execution Engine / Data Providers
```

## 1) Public Interface (Platform API)

### Scope

Public endpoints exposed to clients (CLI, web, OpenClaw, and other agents):

- health
- research
- knowledge (v2)
- conversations (v2)
- strategies
- backtests
- deployments
- portfolios
- orders
- datasets
- data exports/context (v2)

### Contract shape

- URL versioning: `/vN/...`
- Auth: bearer token or API key
- Error envelope: standardized (`ErrorResponse`)
- Idempotency: required for side-effecting POST endpoints
- Pagination: cursor-based (`nextCursor`)

See the OpenAPI file for exact request/response schemas.

### Client Lane Contract (OC-01)

OpenClaw is a first-class **client lane** with the same boundary rules as web and CLI.

Required client-lane rules:

1. OpenClaw calls Platform API contracts only.
2. OpenClaw can use direct SDK/API calls or CLI-mediated calls.
3. OpenClaw does not call provider APIs directly (Lona, execution engines, data vendors).
4. Provider calls remain isolated inside platform adapters.
5. OpenClaw does not introduce dedicated `/v1/openclaw/*` endpoints.

### Conversation Contract (CONV-01)

Conversation behavior is modeled as additive `/v2` API contract, not ad-hoc client-only semantics.

Conversation endpoints:

- `POST /v2/conversations/sessions`
- `GET /v2/conversations/sessions/{sessionId}`
- `POST /v2/conversations/sessions/{sessionId}/turns`

Conversation channel is explicit and normalized by schema enum:

- `cli`
- `web`
- `openclaw`

Context memory rules (CONV-02):

1. Conversation context memory is maintained per `tenant_id:user_id` and synchronized into session metadata.
2. Multi-turn memory tracks recent messages, inferred intent, linked artifacts (strategy/deployment/order/portfolio/backtest/dataset), and symbols.
3. Retention is explicit and bounded by memory policy (`maxRecentMessages`).
4. Turn responses carry a `contextMemorySnapshot` in metadata for deterministic client behavior.

Proactive pipeline rules (CONV-03):

1. Proactive suggestions are derived from turn intent and context memory signals.
2. Proactive notifications require explicit session opt-in (`notificationsOptIn`).
3. Emitted notifications are auditable with persisted records (session, turn, severity, category, request identity).
4. Opt-out sessions continue receiving non-invasive suggestions without notification delivery.

## 2) Internal Adapter Contracts

These interfaces are implementation contracts inside the platform.

### LonaAdapter

```ts
export interface LonaAdapter {
  createStrategyFromDescription(input: {
    name?: string;
    description: string;
    provider?: 'xai';
    tenantId: string;
    userId: string;
  }): Promise<{
    providerRefId: string;
    name: string;
    explanation?: string;
  }>;

  runBacktest(input: {
    providerRefId: string;
    dataIds: string[];
    startDate: string;
    endDate: string;
    initialCash?: number;
    tenantId: string;
    userId: string;
  }): Promise<{ providerReportId: string }>;

  getBacktestReport(input: {
    providerReportId: string;
    tenantId: string;
    userId: string;
  }): Promise<{
    status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
    metrics?: {
      sharpeRatio?: number;
      maxDrawdownPct?: number;
      winRatePct?: number;
      totalReturnPct?: number;
    };
    error?: string;
  }>;

  listSymbols(input: {
    isGlobal?: boolean;
    limit?: number;
    tenantId: string;
    userId: string;
  }): Promise<Array<{ id: string; name: string }>>;

  downloadMarketData(input: {
    symbol: string;
    interval: string;
    startDate: string;
    endDate: string;
    tenantId: string;
    userId: string;
  }): Promise<{ dataId: string }>;
}
```

### ExecutionAdapter

```ts
export interface ExecutionAdapter {
  createDeployment(input: {
    strategyId: string;
    mode: 'paper' | 'live';
    capital: number;
    tenantId: string;
    userId: string;
    idempotencyKey: string;
  }): Promise<{ providerDeploymentId: string; status: 'queued' | 'running' }>;

  stopDeployment(input: {
    providerDeploymentId: string;
    reason?: string;
    tenantId: string;
    userId: string;
  }): Promise<{ status: 'stopping' | 'stopped' }>;

  getDeployment(input: {
    providerDeploymentId: string;
    tenantId: string;
    userId: string;
  }): Promise<{
    status: 'queued' | 'running' | 'paused' | 'stopping' | 'stopped' | 'failed';
    latestPnl?: number;
  }>;

  placeOrder(input: {
    symbol: string;
    side: 'buy' | 'sell';
    type: 'market' | 'limit';
    quantity: number;
    price?: number;
    deploymentId?: string;
    tenantId: string;
    userId: string;
    idempotencyKey: string;
  }): Promise<{ providerOrderId: string; status: 'pending' | 'filled' }>;

  cancelOrder(input: {
    providerOrderId: string;
    tenantId: string;
    userId: string;
  }): Promise<{ status: 'cancelled' | 'failed' }>;

  getPortfolioSnapshot(input: {
    portfolioId: string;
    tenantId: string;
    userId: string;
  }): Promise<{
    cash: number;
    totalValue: number;
    pnlTotal?: number;
    positions: Array<{
      symbol: string;
      quantity: number;
      avgPrice: number;
      currentPrice: number;
      unrealizedPnl: number;
    }>;
  }>;
}
```

### DataKnowledgeAdapter

```ts
export interface DataKnowledgeAdapter {
  initUpload(input: {
    filename: string;
    contentType: string;
    sizeBytes: number;
    tenantId: string;
    userId: string;
  }): Promise<{
    datasetId: string;
    uploadUrl: string;
  }>;

  completeUpload(input: {
    datasetId: string;
    uploadToken?: string;
    tenantId: string;
    userId: string;
  }): Promise<{ status: 'uploaded' | 'failed' }>;

  validateDataset(input: {
    datasetId: string;
    columnMapping: Record<string, string>;
    tenantId: string;
    userId: string;
  }): Promise<{ status: 'queued' | 'running' | 'completed' | 'failed' }>;

  transformDataset(input: {
    datasetId: string;
    targetType: 'candles';
    frequency: string;
    tenantId: string;
    userId: string;
  }): Promise<{ outputDatasetId: string; status: 'queued' | 'running' | 'completed' | 'failed' }>;

  publishToLona(input: {
    datasetId: string;
    mode: 'explicit' | 'just_in_time';
    tenantId: string;
    userId: string;
  }): Promise<{ providerDataId: string; status: 'queued' | 'running' | 'completed' | 'failed' }>;

  getMarketContext(input: {
    assetClasses: string[];
    tenantId: string;
    userId: string;
  }): Promise<{
    regimeSummary: string;
    signals: Array<{ name: string; value: string }>;
  }>;
}
```

## 3) Identity Contract

Every request crossing module boundaries must carry:

- `tenant_id` (string)
- `user_id` (string)
- `request_id` (string)

No service is allowed to synthesize fallback identities for production flows.

## 4) Async Resource Contract

Long-running operations use resource status:

- `queued`
- `running`
- `completed`
- `failed`
- `cancelled`

Affected resources:

- backtests
- datasets (public API surface is active in `/v1/datasets*`; Gate2 thin-stub runtime)
- deployments
- research jobs (if promoted to async)

## 5) Orchestrator State Contract (AG-ORCH-01)

Orchestrator runtime state is deterministic and machine-readable with the following states:

- `received`
- `queued`
- `executing`
- `awaiting_tool`
- `awaiting_user_confirmation`
- `completed`
- `failed`
- `cancelled`

Transition rules:

1. `received` can advance to `queued`, `failed`, or `cancelled`.
2. `queued` can advance to `executing`, `failed`, or `cancelled`.
3. `executing` can move to `awaiting_tool`, `awaiting_user_confirmation`, `completed`, `failed`, or `cancelled`.
4. `awaiting_tool` and `awaiting_user_confirmation` can return only to `executing`, or end in `failed`/`cancelled`.
5. Terminal states are immutable: `completed`, `failed`, and `cancelled` cannot transition to any different state.

## 6) Risk Policy Schema Contract (AG-RISK-01)

Risk policy is defined as a machine-readable, versioned schema:

- `/contracts/schemas/risk-policy.v1.schema.json`

Required top-level fields:

- `version`
- `mode`
- `limits`
- `killSwitch`
- `actionsOnBreach`

Version and validation rules:

1. Current supported version is `risk-policy.v1`.
2. `mode` is constrained to `advisory | enforced`.
3. `limits` must define notional, position, drawdown, and daily-loss bounds with non-negative values.
4. `killSwitch` must include at least `enabled` and may carry trigger metadata.
5. `actionsOnBreach` is required and must contain one or more canonical breach actions.
6. Invalid schema structure or unsupported version must fail validation.
7. Pre-trade execution side effects (`create_deployment`, `create_order`) must pass risk checks before adapter calls.
8. Runtime drawdown breaches (`latestPnl` vs deployment capital) must trigger kill-switch and halt active deployments before further side effects.
9. Every risk decision path (`approved` and `blocked`) must persist an audit record with request identity and outcome metadata.

## 7) Execution Command Boundary (AG-EXE-01)

Execution side effects are mediated by an internal command layer that delegates only to `ExecutionAdapter`.

Required rules:

1. Side-effecting execution paths (`create_deployment`, `stop_deployment`, `place_order`, `cancel_order`) execute through command objects.
2. The command layer is the only component that can call side-effecting adapter operations.
3. Read-only status/snapshot calls can use adapter read methods directly.
4. Risk gating remains mandatory before command execution for side-effecting actions.
5. Command-layer idempotency is mandatory for deployment creation and order placement; duplicate keys replay prior response.
6. Reusing an idempotency key with different command payload must fail with conflict (`IDEMPOTENCY_KEY_CONFLICT`).

## 8) Compatibility Rules

1. Public API changes follow semantic versioning and `/vN` URLs.
2. Internal adapter interfaces can evolve, but each change must be released with adapter tests.
3. Existing fields are never repurposed with different meaning.
4. Deprecated fields must have a removal date.

## 9) Team Independence Checklist

A workstream is considered independent when:

1. It depends only on OpenAPI schema and generated SDK/mocks.
2. It does not import provider SDKs directly in client code.
3. It passes contract tests against mock responses.
4. It does not require undocumented endpoints.

## 10) Migration Notes from Prototype Interfaces

Prototype routes that do not match OpenAPI should be treated as `legacy` and excluded from new integrations.

Examples of migration direction:

- direct CLI calls to provider APIs -> replace with Platform API SDK calls,
- provider-specific response payloads -> normalize to API schemas,
- ad-hoc error payloads -> replace with `ErrorResponse`.

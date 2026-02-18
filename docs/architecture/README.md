# Trade Nexus Architecture

## Status

This folder now contains the **to-be architecture baseline** for contract-first development.

If any document conflicts with implementation prototypes, treat these files as authoritative:

1. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/TARGET_ARCHITECTURE_V2.md`
2. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/INTERFACES.md`
3. `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/specs/platform-api.openapi.yaml`

## Core Direction

1. Platform API is the single public backend contract.
2. CLI is external (`trading-cli` repo) and consumes Platform API only.
3. Lona stays as fixed external dependency through adapter boundaries.
4. Execution engines (live-engine or future alternatives) are replaceable behind an internal adapter.

## Document Map

| Document | Purpose |
|----------|---------|
| [TARGET_ARCHITECTURE_V2.md](./TARGET_ARCHITECTURE_V2.md) | Final to-be architecture and boundaries |
| [INTERFACES.md](./INTERFACES.md) | Interface model (public + internal adapters) |
| [API_CONTRACT_GOVERNANCE.md](./API_CONTRACT_GOVERNANCE.md) | How contracts are changed safely |
| [DOCUMENTATION_IA_AND_GOVERNANCE.md](./DOCUMENTATION_IA_AND_GOVERNANCE.md) | Canonical docs IA, ownership, and gate governance |
| [GAP_ANALYSIS_ASIS_TOBE.md](./GAP_ANALYSIS_ASIS_TOBE.md) | As-is gaps and exact change proposals |
| [DELIVERY_PLAN_AND_TEAM_TOPOLOGY.md](./DELIVERY_PLAN_AND_TEAM_TOPOLOGY.md) | Delegation model, repo plan, and ticket sectors |
| [STRATEGY_VALIDATION_AND_REVIEW_LAYER.md](./STRATEGY_VALIDATION_AND_REVIEW_LAYER.md) | JSON-first validation layer, review workflows, and regression gates |
| [DATA_LIFECYCLE_AND_LONA_CONNECTOR_V2.md](./DATA_LIFECYCLE_AND_LONA_CONNECTOR_V2.md) | Large-file data lifecycle and Lona-compatible publish connector |
| [GATE_TEAM_EXECUTION_PLAYBOOK.md](./GATE_TEAM_EXECUTION_PLAYBOOK.md) | Team/gate operating model and update templates |
| [decisions/](./decisions/) | Architecture decision records (ADRs) for binding program choices |
| [specs/platform-api.openapi.yaml](./specs/platform-api.openapi.yaml) | Canonical public API specification |

Legacy deep-dive documents remain useful for historical context and implementation notes:

- [AGENT_ARCHITECTURE.md](./AGENT_ARCHITECTURE.md)
- [DATA_MODULE.md](./DATA_MODULE.md)
- [KNOWLEDGE_BASE.md](./KNOWLEDGE_BASE.md)
- [CLI_INTERFACE.md](./CLI_INTERFACE.md)
- [OPENCLAW_INTEGRATION.md](./OPENCLAW_INTEGRATION.md)
- [DEPLOYMENT.md](./DEPLOYMENT.md)

## Parallel Workstreams

### Stream A: Contract and SDK

- own OpenAPI and schema versioning,
- generate SDK and mocks,
- enforce contract tests.

### Stream B: Platform Domain Services

- strategy, backtest, deployment, portfolio, order services,
- adapter orchestration,
- policy and risk checks.

### Stream C: Provider Adapters

- Lona adapter,
- execution adapter (live-engine implementation first),
- data/knowledge adapter.

### Stream D: Clients

- external CLI (`trading-cli`) using generated SDK,
- web and agent clients using same API.

## Delivery Rule

No new external endpoint or client integration is allowed unless:

1. It exists in `platform-api.openapi.yaml`.
2. It passes contract tests.
3. Generated SDK is updated.

# Gap Analysis: As-Is vs Target Architecture v2

This document translates architecture findings into concrete change proposals.

## Summary

- **As-is**: multiple direct integrations, drifting contracts, mixed endpoint models.
- **To-be**: one public Platform API contract, adapter boundaries, external CLI consuming generated SDK.

## Gaps and Proposals

| ID | Area | As-Is | To-Be | Gap | Proposal |
|----|------|-------|-------|-----|----------|
| G1 | Public contracts | `INTERFACES.md` and implementation drift | OpenAPI file is canonical | Teams cannot trust contracts | Adopt `/docs/architecture/specs/platform-api.openapi.yaml` as source of truth and generate SDK/mocks from it |
| G2 | CLI boundary | CLI calls Lona and live-engine directly | CLI calls Platform API only | Coupling blocks backend refactors | Move CLI to external repo (`trading-cli`) and remove direct provider calls |
| G3 | Execution abstraction | live-engine API shape leaks into product architecture | Execution behind internal adapter | Provider lock-in and endpoint drift | Implement `ExecutionAdapter`; make live-engine one implementation |
| G4 | Lona integration surface | Mixed direct and proxy styles | One `LonaAdapter` in platform | Duplicate logic and auth inconsistencies | Centralize all Lona access in Platform API adapter layer |
| G5 | Identity propagation | Multiple user-id formats and defaults | Canonical `tenant_id` + `user_id` propagated end-to-end | Risk of cross-tenant data access | Define identity contract and required headers for all adapter calls |
| G6 | Async operations | Mixed sync/async behavior | Explicit job/resource status lifecycle | Unclear client behavior on long tasks | Standardize backtest/deploy/research as async resources |
| G7 | Error semantics | Different error response shapes | One error envelope | Difficult retries and client handling | Use shared `ErrorResponse` schema across all endpoints |
| G8 | Idempotency | Not uniformly enforced | Required for write endpoints with side effects | Duplicate trades/deployments possible | Require `Idempotency-Key` for `POST /orders` and `POST /deployments` |
| G9 | Deployment docs | Contradictory infra directions | Single approved runtime profile per phase | Team confusion and inconsistent delivery | Split docs into "Current runtime" and "Future options" with explicit status |
| G10 | Workstream ownership | Owners set to TBD | Named owners and handoff contracts | Delays and unresolved decisions | Assign DRI per context and API tag |

## Required Changes by Document

### `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/README.md`

- Reframe architecture around Platform API as single public boundary.
- Set CLI as external consumer repo.
- Link to target architecture and OpenAPI source.

### `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/INTERFACES.md`

- Replace ad-hoc endpoint lists with contract-governance rules.
- Define internal adapter interfaces and compatibility policy.
- Link to OpenAPI file for endpoint truth.

### New docs

- `TARGET_ARCHITECTURE_V2.md`: final to-be architecture.
- `API_CONTRACT_GOVERNANCE.md`: process and rules for safe parallel work.
- `specs/platform-api.openapi.yaml`: executable contract baseline.

## Implementation Sequence

### Step 1: Contract foundation (Week 1)

1. Freeze OpenAPI v1 baseline.
2. Generate typed SDK and mock server from spec.
3. Gate merges on spec validation + SDK generation.

### Step 2: Boundary refactor (Week 2)

1. Introduce `LonaAdapter` and `ExecutionAdapter` interfaces.
2. Route all platform operations through adapters.
3. Add adapter contract tests with fixture-based responses.

### Step 3: Client decoupling (Week 3)

1. Create `trading-cli` external repo.
2. Port commands to generated SDK.
3. Remove direct CLI dependencies on provider APIs.

### Step 4: Hardening (Week 4)

1. Enforce idempotency keys and standardized errors.
2. Add end-to-end request tracing.
3. Document operation runbooks and SLOs.

## Definition of Done

1. A developer can implement any feature from OpenAPI + mocks without reading provider code.
2. Switching execution backend does not change client code.
3. All breaking changes require explicit API version bump.
4. All architecture docs reference the same canonical contract source.

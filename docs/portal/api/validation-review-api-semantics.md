---
title: Validation Review API Contracts And Response Semantics
summary: Contract-first endpoint and payload semantics for validation review web/API integrations.
owners:
  - Validation Review Web Docs
updated: 2026-02-20
---

# Validation Review API Contracts And Response Semantics

## Canonical Contract Source

Validation review APIs are defined in `/docs/architecture/specs/platform-api.openapi.yaml` under the `Validation` tag.

## Endpoint Matrix

| Route | OperationId | Success Code | Semantics |
| --- | --- | --- | --- |
| `POST /v2/validation-runs` | `createValidationRunV2` | `202` | Starts a validation run and returns queued/accepted run metadata. |
| `GET /v2/validation-runs/{runId}` | `getValidationRunV2` | `200` | Returns run status (`queued`, `running`, `completed`, `failed`) and final decision state. |
| `GET /v2/validation-runs/{runId}/artifact` | `getValidationRunArtifactV2` | `200` | Returns canonical artifact payload (`validation_run` or compact snapshot). |
| `POST /v2/validation-runs/{runId}/review` | `submitValidationRunReviewV2` | `202` | Accepts trader/agent review decision for the run. |
| `POST /v2/validation-runs/{runId}/render` | `createValidationRunRenderV2` | `202` | Queues optional HTML/PDF render generation from canonical JSON. |
| `POST /v2/validation-baselines` | `createValidationBaselineV2` | `201` | Promotes an existing run as baseline for replay/regression checks. |
| `POST /v2/validation-regressions/replay` | `replayValidationRegressionV2` | `202` | Compares baseline vs candidate run and returns merge/release gate decisions. |

## Canonical Artifact Semantics

1. `validation_run` JSON is authoritative for merge/release and audit.
2. `validation_llm_snapshot` is a compact derivative for agent analysis.
3. Render artifacts (`html`, `pdf`) are derived and must not replace canonical JSON records.
4. `finalDecision` uses contract enum values: `pass`, `conditional_pass`, `fail`.

## Review Decision Semantics

1. `reviewerType` is constrained to `agent` or `trader`.
2. `decision` is constrained to `pass`, `conditional_pass`, or `fail`.
3. `findings` are structured entries with `priority`, `confidence`, `summary`, and `evidenceRefs`.
4. Trader review is policy-controlled (`requireTraderReview`) and optional by profile.

## Identity, Auth, and Request Correlation

1. Clients authenticate with bearer token or API key per OpenAPI security schemes.
2. User/tenant scope must be derived from authenticated session context, not caller-provided identity headers.
3. `X-Request-Id` is used for trace correlation across web proxy and Platform API.
4. `Idempotency-Key` should be supplied for write calls (`POST`) to avoid duplicate effects.

## Error and Retry Semantics

1. `400` indicates invalid payload or policy shape.
2. `401` indicates missing/invalid auth context.
3. `404` indicates unknown run/baseline resource.
4. Retrying write calls should reuse the same `Idempotency-Key` only when payload is unchanged.

## Governance Checks

Run these checks for contract and docs alignment:

```bash
npx --yes --package=@redocly/cli@1.34.5 redocly lint docs/architecture/specs/platform-api.openapi.yaml
pytest backend/tests/contracts/test_openapi_contract_v2_validation_freeze.py
pytest backend/tests/contracts/test_platform_api_v2_handlers.py
npm --prefix docs/portal-site run ci
```

## Traceability

- Child issue: [#282](https://github.com/iamtxena/trade-nexus/issues/282)
- Parent issue: [#288](https://github.com/iamtxena/trade-nexus/issues/288)
- Validation web proxy auth: `/frontend/src/lib/validation/server/auth.ts`
- Validation web proxy transport: `/frontend/src/lib/validation/server/platform-api.ts`
- Contract governance: `/.github/workflows/contracts-governance.yml`
- Docs governance: `/.github/workflows/docs-governance.yml`

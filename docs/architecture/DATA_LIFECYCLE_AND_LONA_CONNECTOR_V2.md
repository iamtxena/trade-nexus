# Data Lifecycle and Lona Connector v2

## Purpose

Define a scalable data architecture that supports large uploads (GB scale), validation, transformation, and backtesting integration while keeping Lona unchanged.

This document is the canonical design addendum for:

1. user-provided dataset ingestion,
2. dataset processing and quality validation,
3. Lona-compatible publish flow through an adapter boundary.

## Non-Negotiable Constraints

1. Lona internals are not changed in this phase.
2. Platform API remains the only public backend interface.
3. Data processing runs in the Data Module (`trader-data`) as source of truth.
4. All long-running data tasks are async and status-driven.

## Supported Use Cases

1. User uploads already prepared data and uses it for strategy/backtest.
2. User uploads raw data that needs platform-side preprocessing before backtest.
3. User reuses existing Lona/global assets without duplicating source data.
4. User requests externally fetched data (example: BTC for last N months).
5. User uploads BBO/trades and requests conversion to candles.

## Architecture Model

### Control Plane

Owned by Trade Nexus Platform API:

- dataset metadata registry,
- job orchestration and status tracking,
- tenant/user authorization and policy checks,
- backtest orchestration using dataset references.

### Data Plane

Owned by Data Module (`trader-data`):

- object storage for raw and derived artifacts,
- streaming/chunked upload completion,
- validation and transform workers,
- Lona publish connector workflow.

### Provider Plane

Lona remains external:

- receives publish-ready, Lona-compatible datasets,
- continues running strategy generation and backtests as-is.

## Dataset Lifecycle

State machine:

1. `uploading`
2. `uploaded`
3. `validating`
4. `validated` | `validation_failed`
5. `transforming`
6. `ready` | `transform_failed`
7. `publishing_lona`
8. `published_lona` | `publish_failed`
9. `archived`

Rules:

1. immutable dataset version per completed upload,
2. all transitions logged with `tenant_id`, `user_id`, `request_id`,
3. retry-safe operations using idempotency keys.

## Worker Topology

### `ingest-worker`

- finalizes upload session,
- computes artifact metadata (size, format, checksum),
- registers dataset version.

### `validate-worker`

- validates required schema and column mapping,
- validates timestamp order/duplicates/null handling,
- writes machine-readable quality report.

### `transform-worker`

- executes user-requested transforms (for example BBO/trades -> candles),
- produces derived dataset versions with lineage links.

### `lona-publish-worker`

- converts selected dataset version into Lona-compatible shape,
- publishes by existing Lona API contract,
- stores cross-reference (`dataset_version_id <-> lona_symbol_id`).

## Lona Compatibility Strategy (No Lona Internal Changes)

Use a publish connector with two modes:

1. **Explicit publish**: user requests publish and reuses published artifact.
2. **Just-in-time publish**: on backtest request, only required slice is published.

Why this works:

1. simulator contract is already file-path + column mapping based,
2. avoids pushing full raw datasets through Lona,
3. keeps Lona behavior stable while enabling large upstream datasets.

## API Contract Additions (Planned)

Add to Platform OpenAPI:

1. `POST /v1/datasets/uploads:init`
2. `POST /v1/datasets/{dataset_id}/uploads:complete`
3. `POST /v1/datasets/{dataset_id}/validate`
4. `POST /v1/datasets/{dataset_id}/transform/candles`
5. `POST /v1/datasets/{dataset_id}/publish/lona`
6. `GET /v1/datasets`
7. `GET /v1/datasets/{dataset_id}`
8. `GET /v1/datasets/{dataset_id}/quality-report`

Backtest contract update:

- accept dataset references as primary input and resolve provider refs internally.

## Team Ownership

1. Team A (Contracts): OpenAPI/SDK/mocks for dataset lifecycle.
2. Team B (Platform): orchestration, job status, backtest dataset resolution.
3. Data/Knowledge Team: ingestion, validation, transform, lineage.
4. Team C (Lona Integration): publish connector and mapping normalization.
5. Team E (CLI/OpenClaw): dataset commands over Platform API only.
6. Team F (Reliability): SLOs, queues, retries, and runbook checks.

## Gate Mapping

### Gate G2 (Contract + thin vertical slice)

1. define dataset lifecycle contracts,
2. implement minimal upload -> validate -> publish -> backtest happy path,
3. verify no direct client calls to Lona.

### Gate G3 (Scale and hardening)

1. large-file ingestion path and async workers,
2. transform pipelines and quality reports,
3. just-in-time publish and failure/retry semantics.

### Gate G4 (Operational maturity)

1. SLO and alerting for dataset jobs,
2. lineage/audit exports,
3. recovery playbooks and reconciliation checks.

## Acceptance Criteria

1. Users can upload data larger than multipart limits through async flow.
2. Validation occurs before simulation execution.
3. Backtests run without requiring Lona internal architecture changes.
4. Dataset lineage is traceable from raw upload to Lona publish ID.
5. CLI/Web/OpenClaw all use the same Platform API dataset contract.

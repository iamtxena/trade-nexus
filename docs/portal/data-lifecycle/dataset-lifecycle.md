---
title: Dataset Lifecycle
summary: Documentation entrypoint for dataset ingest, validation, publication, and backtest consumption.
owners:
  - Gate1 Docs Team
updated: 2026-02-14
---

# Dataset Lifecycle

Data lifecycle behavior is documented and implemented behind architecture boundaries.

## Lifecycle Phases

1. Ingest raw data.
2. Validate schema and quality.
3. Publish versioned dataset.
4. Reference dataset in backtest/deployment workflows.

## Contract Status

- Dataset lifecycle API endpoints are part of the canonical OpenAPI v1 contract.
- Active dataset routes are:
  - `POST /v1/datasets/uploads:init`
  - `POST /v1/datasets/{datasetId}/uploads:complete`
  - `POST /v1/datasets/{datasetId}/validate`
  - `POST /v1/datasets/{datasetId}/transform/candles`
  - `POST /v1/datasets/{datasetId}/publish/lona`
  - `GET /v1/datasets`
  - `GET /v1/datasets/{datasetId}`
  - `GET /v1/datasets/{datasetId}/quality-report`
- Gate2 implementation is a thin-stub baseline for orchestration and contract flow.

## Canonical References

- `/docs/architecture/DATA_LIFECYCLE_AND_LONA_CONNECTOR_V2.md`
- `/docs/architecture/TARGET_ARCHITECTURE_V2.md`
- `/docs/architecture/INTERFACES.md`

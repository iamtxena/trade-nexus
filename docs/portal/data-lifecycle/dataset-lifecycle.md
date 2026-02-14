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

- Dataset lifecycle API endpoints are planned for Gate2 (`#97`).
- Current canonical OpenAPI v1 does not include `/v1/datasets` routes.
- Until `#97` lands, treat dataset lifecycle as planned interface work, not active public v1 contract.

## Canonical References

- `/docs/architecture/DATA_LIFECYCLE_AND_LONA_CONNECTOR_V2.md`
- `/docs/architecture/TARGET_ARCHITECTURE_V2.md`
- `/docs/architecture/INTERFACES.md`

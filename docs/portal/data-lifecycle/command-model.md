---
title: Dataset Lifecycle Command Model
summary: Baseline command model for dataset ingest, validation, publication, and usage.
owners:
  - Gate1 Docs Team
updated: 2026-02-14
---

# Dataset Lifecycle Command Model

## Lifecycle Steps

1. Ingest raw dataset.
2. Validate schema and quality.
3. Publish dataset version.
4. Reference published dataset in backtest and deployment workflows.

## Command Model

- `trading-cli dataset ingest`
- `trading-cli dataset validate`
- `trading-cli dataset publish`
- `trading-cli backtest run --dataset-ref <id>`
- `trading-cli deploy start --dataset-ref <id>`

## Boundaries

- CLI and clients do not call provider APIs directly.
- Dataset handling is performed through Platform API surfaces.
- Dataset lifecycle endpoints are planned for Gate2 (`#97`) and are not in the current OpenAPI v1 path set.
- Data module implementation details are owned in [`trader-data`](https://github.com/iamtxena/trader-data).

## References

- Dataset lifecycle architecture: `/docs/architecture/DATA_LIFECYCLE_AND_LONA_CONNECTOR_V2.md`
- Contract boundaries: `/docs/architecture/INTERFACES.md`

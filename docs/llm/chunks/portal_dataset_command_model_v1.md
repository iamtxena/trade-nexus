# Dataset Lifecycle Command Model

Source: `docs/portal/data-lifecycle/command-model.md`
Topic: `data`
Stable ID: `portal_dataset_command_model_v1`

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
- Data module implementation details are owned in [`trader-data`](https://github.com/iamtxena/trader-data).

## References

- Dataset lifecycle architecture: `/docs/architecture/DATA_LIFECYCLE_AND_LONA_CONNECTOR_V2.md`
- Contract boundaries: `/docs/architecture/INTERFACES.md`

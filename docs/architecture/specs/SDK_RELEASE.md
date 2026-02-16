# SDK Release Workflow (`@trade-nexus/sdk`)

This document describes how the SDK publishing pipeline works from the
canonical OpenAPI source.

## Workflow file

- `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/.github/workflows/publish-sdk.yml`

## Triggers

1. `workflow_dispatch`:
   - default is dry-run (`publish=false`)
   - set `publish=true` to publish to npm
2. `push` on tags matching `sdk-v*`:
   - publishes automatically

## Required repository secret

- `NPM_TOKEN` (npm automation token with publish access for `@trade-nexus/sdk`)

## Release gates in workflow

1. Regenerate SDK from canonical OpenAPI:
   - `bash contracts/scripts/generate-sdk.sh`
2. Drift verification:
   - `bash contracts/scripts/verify-sdk-drift.sh`
3. Release preparation:
   - `bash contracts/scripts/prepare-sdk-release.sh`
   - enforces OpenAPI version == SDK package version
   - enforces tag format `sdk-v<version>` on tag-triggered runs
   - runs SDK build and package dry-run

## Post-generation normalizations

`contracts/scripts/generate-sdk.sh` applies deterministic normalizations after OpenAPI generation so the published SDK matches the API contract and consumer expectations:

- `BacktestsApi` request parameter is normalized to required `CreateBacktestRequest` (non-null).
- `BacktestDataExportResponse` public field is normalized to `export` (not `_export`) to match the OpenAPI response shape.

## Local validation command

```bash
bash /Users/txena/sandbox/16.enjoy/trading/trade-nexus/contracts/scripts/prepare-sdk-release.sh
```

This command is the same release-prep gate used by the workflow.

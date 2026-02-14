---
title: Troubleshooting
summary: Baseline troubleshooting map for contract, SDK, mock server, and docs workflows.
owners:
  - Gate1 Docs Team
updated: 2026-02-14
---

# Troubleshooting

## Contract and SDK

- Re-run contract tests: `uv run --with pytest python -m pytest backend/tests/contracts/test_openapi_contract_baseline.py backend/tests/contracts/test_openapi_contract_freeze.py`
- Regenerate SDK: `bash contracts/scripts/generate-sdk.sh`
- Verify SDK drift: `bash contracts/scripts/verify-sdk-drift.sh`

## Mock and Breaking Changes

- Run mock smoke tests: `bash contracts/scripts/mock-smoke-test.sh`
- Run breaking-change guard (PR mode): `GITHUB_EVENT_NAME=pull_request GITHUB_BASE_REF=main bash contracts/scripts/check-breaking-changes.sh`

## Docs Pipeline

- Regenerate API reference: `npm --prefix docs/portal-site run api:build`
- Validate docs checks:
  - `python3 scripts/docs/check_frontmatter.py`
  - `python3 scripts/docs/check_links.py`
  - `python3 scripts/docs/check_stale_references.py`
  - `npm --prefix docs/portal-site run build`

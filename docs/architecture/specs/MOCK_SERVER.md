# Platform API Mock Server (Gate1)

This runbook describes how to run the generated mock server from the canonical
OpenAPI source and validate that all v1 routes are reachable for consumer tests.

## Canonical contract source

- `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/docs/architecture/specs/platform-api.openapi.yaml`

## Start mock server

```bash
bash /Users/txena/sandbox/16.enjoy/trading/trade-nexus/contracts/scripts/run-mock-server.sh
```

Optional env vars:

- `PRISM_HOST` (default: `127.0.0.1`)
- `PRISM_PORT` (default: `4010`)
- `NPM_CONFIG_CACHE` (default: `/tmp/trade-nexus-npm-cache`)

## Run smoke tests

```bash
bash /Users/txena/sandbox/16.enjoy/trading/trade-nexus/contracts/scripts/mock-smoke-test.sh
```

The smoke suite validates all v1 operations and fails if any operation returns
`404` or `405` (missing or wrong route/method mapping).

## Fixtures

Sample request payloads used by smoke tests are under:

- `/Users/txena/sandbox/16.enjoy/trading/trade-nexus/contracts/fixtures`

These fixtures can also be reused by downstream consumer-driven tests.

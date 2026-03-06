---
title: Authenticate CLI
summary: End-user quickstart for human and bot authentication in trading-cli.
owners:
  - Gate1 Docs Team
updated: 2026-03-04
---

# Authenticate CLI

Use this guide to establish and validate `trading-cli` authentication before running strategy, backtest, deployment, or validation workflows.

## Quickstart

### Login (human auth)

```bash
export PLATFORM_API_BASE_URL="https://api-nexus.lona.agency"
export PLATFORM_API_BEARER_TOKEN="<jwt-access-token>"
trading-cli health get
```

### Whoami (identity/scope check)

```bash
trading-cli bot list
```

### Logout

```bash
unset PLATFORM_API_BEARER_TOKEN PLATFORM_API_TOKEN PLATFORM_API_KEY
```

## Device Auth Scope Matrix

`/v2/validation-cli-auth/device/start` accepts explicit `scopes` and fails closed on unsupported values (`CLI_AUTH_SCOPE_INVALID`).

Default device-login scopes when `scopes` is omitted:
- `validation:read`
- `validation:write`

Supported scopes and command domains:

| Scope | Domain | Representative endpoints | Representative CLI commands |
| --- | --- | --- | --- |
| `validation:read` | Validation read | `GET /v2/validation-runs`, `GET /v2/validation-runs/{runId}` | `trading-cli validation run list`, `trading-cli validation run get --run-id <id>` |
| `validation:write` | Validation write | `POST /v2/validation-runs`, `POST /v2/validation-runs/{runId}/review` | `trading-cli validation run create ...`, `trading-cli validation run review ...` |
| `strategy:read` | Core strategy read | `GET /v1/strategies`, `GET /v1/strategies/{strategyId}` | `trading-cli strategy list`, `trading-cli strategy get --strategy-id <id>` |
| `backtest:read` | Core backtest read | `GET /v1/backtests/{backtestId}` | `trading-cli backtest get --backtest-id <id>` |
| `deployment:read` | Core deployment read | `GET /v1/deployments`, `GET /v1/deployments/{deploymentId}` | `trading-cli deploy list`, `trading-cli deploy get --deployment-id <id>` |

Fail-closed policy for CLI bearer tokens (`tnx.cli...`):
- Missing required scope: `403 CLI_AUTH_SCOPE_FORBIDDEN`
- Endpoint outside authorized CLI scope domains: `403 CLI_AUTH_SCOPE_FORBIDDEN`
- Invalid/revoked/expired CLI token: `401 CLI_ACCESS_TOKEN_INVALID|CLI_ACCESS_TOKEN_REVOKED|CLI_ACCESS_TOKEN_EXPIRED`

## Bot Auth vs Human Auth

| Use case | Credential | Env var | Notes |
| --- | --- | --- | --- |
| Human operator in terminal or CI job with user identity | JWT bearer token | `PLATFORM_API_BEARER_TOKEN` | Preferred for user-scoped operations and invite acceptance flows. |
| Runtime bot automation | Runtime bot key (`tnx.bot.<botId>.<keyId>.<secret>`) | `PLATFORM_API_KEY` | Works for bot actor requests while preserving owner scope in validation flows. |
| Backward compatibility | Bearer token alias | `PLATFORM_API_TOKEN` | Alias for bearer auth; prefer `PLATFORM_API_BEARER_TOKEN` for new setups. |

## Failure Troubleshooting

### Expired Token

Expected error shape:
- `httpStatus: 401`
- `code: "AUTH_UNAUTHORIZED"`

Recovery:
1. Mint a fresh bearer token from your identity provider.
2. Re-export `PLATFORM_API_BEARER_TOKEN`.
3. Re-run:

```bash
trading-cli health get
```

### Revoked Token (Bot Key)

Expected error shape:
- `httpStatus: 401`
- `code: "BOT_API_KEY_REVOKED"`

Recovery:
1. Rotate the bot key:

```bash
trading-cli key rotate --bot-id <bot-id> --reason "replace revoked key"
```

2. Update secret storage with the newly issued key.
3. Retry the failed command with the new `PLATFORM_API_KEY`.

### Unauthorized (Missing/Invalid Credential)

Expected error shape:
- `httpStatus: 401`
- `code: "AUTH_UNAUTHORIZED"` or `code: "BOT_API_KEY_INVALID"`

Recovery:
1. Check auth vars:

```bash
env | rg '^PLATFORM_API_(BEARER_TOKEN|TOKEN|KEY)='
```

2. Ensure `PLATFORM_API_BASE_URL` is set to platform host or local loopback.
3. Retry with request correlation:

```bash
trading-cli bot list --request-id req-cli-auth-check-001
```

## Related Docs

- [CLI Common Workflows](./workflows.md)
- [Operator Runbook: CLI Auth Sessions](../operations/cli-auth-operator-runbook.md)
- [Operations Troubleshooting](../operations/troubleshooting.md)

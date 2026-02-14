---
title: Quickstart
summary: End-user quickstart for research to execution workflows across API and CLI lanes.
owners:
  - Gate1 Docs Team
updated: 2026-02-14
---

# Quickstart

This quickstart covers the baseline Gate0 + Gate1 user journey: research, strategy, backtest, deploy, and monitor.

## Prerequisites

1. Platform contract artifacts are available from `trade-nexus`.
2. CLI client is available from [`trading-cli`](https://github.com/iamtxena/trading-cli).
3. You have environment configuration for Platform API access.

## Workflow Path

1. Research market opportunities.
2. Create or update a strategy.
3. Run backtests against a selected dataset.
4. Start and monitor deployment.
5. Track portfolio and order outcomes.

## API and CLI Mapping

| Workflow | API Lane | CLI Lane |
| --- | --- | --- |
| Research | Platform API `research` operations | `trading-cli research ...` |
| Strategy | Platform API `strategies` operations | `trading-cli strategy ...` |
| Backtest | Platform API `backtests` operations | `trading-cli backtest ...` |
| Deploy | Platform API `deployments` operations | `trading-cli deploy ...` |
| Portfolio/Orders | Platform API `portfolios` and `orders` operations | `trading-cli portfolio ...` / `trading-cli order ...` |

## Next Steps

- Detailed CLI flow: [CLI Common Workflows](../cli/workflows.md)
- Contract boundaries: [Platform API Contract](../api/platform-api.md)
- Troubleshooting: [Troubleshooting](../operations/troubleshooting.md)

---
title: Strategy to Deploy Flow
summary: Canonical CLI flow for strategy creation, backtest execution, deployment, and monitoring.
owners:
  - Gate1 Docs Team
updated: 2026-02-14
---

# Strategy to Deploy Flow

## Flow Stages

1. Research market opportunities.
2. Create strategy definition.
3. Execute backtest with dataset reference.
4. Start deployment from approved strategy/backtest.
5. Monitor deployment, portfolio, and orders.

## Command Model (CLI)

Use this baseline command model for user docs and integration examples:

- `trading-cli research market-scan`
- `trading-cli strategy create`
- `trading-cli strategy update`
- `trading-cli backtest run`
- `trading-cli deploy start`
- `trading-cli deploy stop`
- `trading-cli portfolio show`
- `trading-cli order create`

## Dataset Hand-off

Backtest and deployment inputs must reference dataset artifacts produced through the dataset lifecycle command model.

- Dataset model: [Dataset Lifecycle Command Model](../data-lifecycle/command-model.md)
- Data repository implementation lane: [`trader-data`](https://github.com/iamtxena/trader-data)

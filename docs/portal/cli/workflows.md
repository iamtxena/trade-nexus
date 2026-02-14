---
title: CLI Common Workflows
summary: Baseline workflow map for strategy, backtest, deployment, and portfolio/order operations.
owners:
  - Gate1 Docs Team
updated: 2026-02-14
---

# CLI Common Workflows

`trading-cli` is the external client lane for Platform API consumers.

## Workflow Categories

1. Research and market scanning.
2. Strategy creation and updates.
3. Backtest execution and result inspection.
4. Deployment lifecycle and status checks.
5. Portfolio views and order lifecycle.

## Baseline User Flow

1. Run research scan and shortlist opportunities.
2. Create a strategy draft and iterate on parameters.
3. Execute backtests with dataset references.
4. Deploy a validated strategy to target runtime.
5. Monitor deployment, portfolio, and order status.

Detailed playbook: [Strategy to Deploy Flow](strategy-backtest-deploy.md)

Dataset command model: [Dataset Lifecycle Command Model](../data-lifecycle/command-model.md)

## Usage References

- CLI interface model: `/docs/architecture/CLI_INTERFACE.md`
- Delivery topology: `/docs/architecture/DELIVERY_PLAN_AND_TEAM_TOPOLOGY.md`
- Platform API contract: `/docs/architecture/specs/platform-api.openapi.yaml`

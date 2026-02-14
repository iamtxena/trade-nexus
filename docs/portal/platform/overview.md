---
title: Platform Overview
summary: High-level architecture and repository topology for Trade Nexus platform delivery.
owners:
  - Gate1 Docs Team
updated: 2026-02-14
---

# Platform Overview

Trade Nexus is the orchestration platform for research, strategy management, backtesting, deployment, portfolio tracking, and order execution workflows.

## Core Repositories

- `trade-nexus`: Platform API, architecture, governance, SDK/mock source contract.
- `trading-cli`: External CLI client that consumes Platform API only.
- `trader-data`: Data lifecycle and ingestion boundary implementation.
- `live-engine`: Execution runtime used through adapter contracts.

Repository links:

- [`trade-nexus`](https://github.com/iamtxena/trade-nexus)
- [`trading-cli`](https://github.com/iamtxena/trading-cli)
- [`trader-data`](https://github.com/iamtxena/trader-data)
- [`live-engine`](https://github.com/iamtxena/live-engine)

## Ownership Model

- Parent `#76`: contracts and governance authority.
- Parent `#77`: platform domain services.
- Parent `#78`: data and knowledge boundaries.
- Parent `#79`: execution integration.
- Parent `#80`: client surface and CLI lane.
- Parent `#81`: cross-parent governance and closeout.
- Parent `#106`: docs distribution and documentation quality program.

## Authoritative Architecture Sources

- `/docs/architecture/TARGET_ARCHITECTURE_V2.md`
- `/docs/architecture/DELIVERY_PLAN_AND_TEAM_TOPOLOGY.md`
- `/docs/architecture/INTERFACES.md`

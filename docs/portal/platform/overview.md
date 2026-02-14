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

## Authoritative Architecture Sources

- `/docs/architecture/TARGET_ARCHITECTURE_V2.md`
- `/docs/architecture/DELIVERY_PLAN_AND_TEAM_TOPOLOGY.md`
- `/docs/architecture/INTERFACES.md`

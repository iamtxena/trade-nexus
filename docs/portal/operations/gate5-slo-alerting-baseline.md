---
title: Gate5 SLO And Alerting Baseline
summary: Versioned SLO and alert ownership baseline used by Gate5 release governance checks.
owners:
  - Team F
  - Team G
updated: 2026-02-16
---

# Gate5 SLO And Alerting Baseline

## Objective

Define one explicit, versioned reliability baseline for critical Gate5 runtime paths and enforce it in CI.

## Source Of Truth

1. Baseline version: `gate5-slo-alert-baseline.v1`
2. Versioned config: `contracts/config/slo-alert-baseline.v1.json`
3. Verification gate: `contracts/scripts/check-slo-alert-baseline.py`
4. CI enforcement path: `.github/workflows/contracts-governance.yml`

## SLO Matrix

| SLO ID | Service | Critical Path | SLI | Target | Window | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| `platform_api_request_success_rate` | platform-api | execution,risk,research,reconciliation,conversation | 2xx_or_contractual_4xx_rate | `>=99.5%` | 30d | Team F |
| `risk_pretrade_latency_p95_ms` | risk-pretrade | risk,execution | p95_latency_ms | `<=200` | 7d | Team F |
| `research_market_scan_latency_p95_ms` | research | research | p95_latency_ms | `<=2500` | 7d | Team F |
| `reconciliation_cycle_success_rate` | reconciliation | reconciliation | successful_cycle_rate | `>=99.0%` | 30d | Team F |
| `conversation_turn_latency_p95_ms` | conversation | conversation | p95_latency_ms | `<=1200` | 7d | Team F |

## Alert Matrix

| Alert ID | SLO ID | Condition | Severity | Owner |
| --- | --- | --- | --- | --- |
| `alert_platform_api_success_rate_burn` | `platform_api_request_success_rate` | `error_budget_burn_2h>=5%` | SEV-2 | Team F |
| `alert_risk_pretrade_latency` | `risk_pretrade_latency_p95_ms` | `p95_latency_ms>200_for_15m` | SEV-2 | Team F |
| `alert_research_latency` | `research_market_scan_latency_p95_ms` | `p95_latency_ms>2500_for_15m` | SEV-3 | Team F |
| `alert_reconciliation_success_rate` | `reconciliation_cycle_success_rate` | `successful_cycle_rate<99.0_for_15m` | SEV-2 | Team F |
| `alert_conversation_turn_latency` | `conversation_turn_latency_p95_ms` | `p95_latency_ms>1200_for_15m` | SEV-3 | Team F |

## Governance Rules

1. Any SLO or alert semantics change must update both this portal page and `contracts/config/slo-alert-baseline.v1.json` in the same PR.
2. `contracts/scripts/check-slo-alert-baseline.py` must pass in CI before merge.
3. Missing owner, target, or ID alignment is a release-gating failure for Gate5.

## Traceability

- Reliability parent: `#81`
- Gate5 reliability closure issue: `#45`
- Gate workflow template: `docs/portal/operations/gate-workflow.md`

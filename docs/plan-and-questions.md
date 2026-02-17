# Plan And Questions - Validation Feature Program

Date: 2026-02-17
Status: Working architecture plan (discussion-backed)

## Why This Feature Exists

Trader trust breaks when generated strategy output looks correct in code but chart/report evidence is confusing (example: zig-zag strategy without clearly rendered zig-zag indicator).

Goal: add a validation ecosystem around Lona outputs so every strategy run can be independently verified before trader acceptance.

## Decisions Locked In

1. Lona is treated as a black box.
2. Canonical validation output is JSON-first.
3. HTML/PDF are optional render outputs, generated only when requested.
4. Use Supabase for validation workflow metadata.
5. Use Trade Nexus web lane for reviewer UX.
6. Missing required indicators is a hard fail.
7. Metric drift tolerance is configurable.
8. Trader review is optional per run (switchable), not mandatory for all runs.
9. Regression policy blocks merge and release.

## Validation Lanes

1. Deterministic lane:
   - indicator fidelity checks,
   - trade and execution-log coherence checks,
   - metrics consistency checks.
2. Agent lane:
   - evidence-based review from compact artifact + referenced logs/trades,
   - bounded runtime and tool access.
3. Trader lane:
   - optional review comments and verdict in web UI.

## Performance Control

Use policy profiles to control runtime cost:

1. `FAST`: merge gate, deterministic-heavy, low latency.
2. `STANDARD`: deterministic + compact agent review.
3. `EXPERT`: release/trader requested, deeper review and optional human step.

## Artifact Strategy

1. Canonical:
   - `validation_run.json`
2. Agent-optimized:
   - `validation_llm_snapshot.json`
3. Optional render outputs:
   - `report.html`
   - `report.pdf`

Heavy payloads stay in blob refs, not embedded in compact snapshots.

## Storage Plan

1. Supabase:
   - run metadata,
   - review states,
   - baseline index,
   - policy outcomes.
2. Blob storage:
   - logs, trades, chart payloads, rendered artifacts.
3. Vector memory:
   - indicator expertise,
   - AI findings and trader feedback memory.

## Module Design

Package validation for future portability to Lona layer:

1. `validation-core`
2. `validation-connectors`
3. `validation-store`
4. `validation-render` (optional)

## Open Questions To Resolve With Engineering

1. Which chart payload fields are canonical for indicator presence checks?
2. Should agent review require web-search mode in `EXPERT` profile only?
3. What exact metric drift thresholds should be default per strategy type?
4. Which artifacts must be retained long-term vs TTL expiration?
5. What is the migration path to run this module inside `lona-gateway` later?

## Immediate Next Action

Execute the Validation Program issue wave (V-01..V-12) with independent review gates and architect arbitration.

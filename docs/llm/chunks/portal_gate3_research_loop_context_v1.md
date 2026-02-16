# Gate3 Research Loop with Context

Source: `docs/portal/platform/gate3-research-loop-context.md`
Topic: `platform`
Stable ID: `portal_gate3_research_loop_context_v1`

# Gate3 Research Loop with Context

## Objective

Gate3 extends research flow to consume:

1. Knowledge Base evidence.
2. Data Module market context.

## Runtime Sequence

1. Client calls `POST /v2/research/market-scan`.
2. Platform computes baseline strategy ideas.
3. Platform queries Knowledge Base for relevant evidence.
4. Platform requests contextual market summary from data module adapter.
5. Platform returns enriched response with:
   - `strategyIdeas`
   - `knowledgeEvidence`
   - `dataContextSummary`

## Feedback Loop

After backtest completion, runtime feedback is ingested into KB as `LessonLearned` records.

## Gate3 Non-goals

1. Full conversation UX rollout.
2. OpenClaw expansion.
3. Full ML decision loop rollout.

## Gate5 Extension (ML Safety + Cache Freshness)

Gate5 extends this flow with optional-safe ML enrichment while preserving deterministic behavior:

1. Market context may include `mlSignals` (`prediction`, `sentiment`, `volatility`, `anomaly`, `regime`).
2. Runtime normalizes top-level `sentiment` context fields into canonical `mlSignals.sentiment` before validation/scoring.
3. Research scoring validates signal shapes and confidence before use.
4. Missing/invalid model output falls back to deterministic baseline scoring (no opaque execution side effects).
5. Market context retrieval is cache-backed with explicit TTL and order-insensitive asset keying.
6. Research responses expose fallback state in `dataContextSummary` for auditability.
7. Provider-backed market-scan symbol retrieval is guarded by deterministic budget policy (`maxTotalCostUsd`, `maxPerRequestCostUsd`, `estimatedMarketScanCostUsd`, `spentCostUsd`).
8. Budget breach or invalid policy fails closed before adapter side effects; typed adapter failures release reserved budget and return deterministic fallback responses.
9. Unexpected adapter exceptions release reserved budget and fail closed with an explicit error code.
10. Budget decision events are recorded for auditability.
11. Research loop persists validated anomaly/regime snapshots for downstream risk gating (`__market__` key fallback-safe).
12. Risk pretrade gates apply deterministic regime sizing reduction (`risk_off` + confidence `>=0.55`) and fail closed on anomaly breach (`isAnomaly=true`, `score>=0.8`, `confidence>=0.7`).

Detailed Gate5 ML contracts, fallback matrix, and auditability coverage:

- `/docs/portal/platform/gate5-ml-signal-integration.md`

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

1. Market context may include `mlSignals` (`prediction`, `sentiment`, `volatility`, `anomaly`).
2. Research scoring validates signal shapes and confidence before use.
3. Missing/invalid model output falls back to deterministic baseline scoring (no opaque execution side effects).
4. Market context retrieval is cache-backed with explicit TTL and order-insensitive asset keying.
5. Research responses expose fallback state in `dataContextSummary` for auditability.

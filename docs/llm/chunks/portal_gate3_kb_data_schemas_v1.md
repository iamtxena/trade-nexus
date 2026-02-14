# Gate3 KB and Data Schemas

Source: `docs/portal/data-lifecycle/gate3-kb-data-schemas.md`
Topic: `data_lifecycle`
Stable ID: `portal_gate3_kb_data_schemas_v1`

# Gate3 KB and Data Schemas

## Canonical Knowledge Base Schema

Schema version: `1.0`

Entities:

1. `KnowledgePattern`
2. `MarketRegime`
3. `LessonLearned`
4. `MacroEvent`
5. `CorrelationEdge`

Authoritative artifacts:

- `trade-nexus/backend/src/platform_api/knowledge/models.py`
- `trade-nexus/supabase/migrations/002_kb_schema.sql`

## Canonical Market Data Model

Schema version: `1.0`

Entities:

1. `TickV1`
2. `OrderBookSnapshotV1`
3. `CandleV1`
4. `ContextualCandleV1`

Authoritative artifacts:

- `trader-data/src/trader_data/models/market_data.py`

## Pipeline Ownership

- Platform control-plane and public APIs: `trade-nexus`
- Data ingest/filter/transform/export workers: `trader-data`
- Engine execution internals: `live-engine`

## Internal Service Boundary

`trader-data` exposes internal authenticated routes under `/internal/v1/*`.
External clients still enter only through Platform API.

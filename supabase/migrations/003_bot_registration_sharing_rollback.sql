-- ROLLBACK for Migration 003: Bot Registration + Validation Sharing
-- Run this to fully reverse migration 003
-- Order matters: drop dependents first

-- =============================================================
-- 1. Drop sharing tables (depends on validation_runs)
-- =============================================================
drop policy if exists "share_creator_all" on validation_run_shares;
drop policy if exists "share_recipient_select" on validation_run_shares;
drop table if exists validation_run_shares;

-- =============================================================
-- 2. Drop validation_runs (depends on bots, strategies)
-- =============================================================
drop policy if exists "validation_run_owner_all" on validation_runs;
drop policy if exists "validation_run_shared_select" on validation_runs;
drop table if exists validation_runs;

-- =============================================================
-- 3. Drop bot_api_keys (depends on bots)
-- =============================================================
drop policy if exists "bot_key_owner_all" on bot_api_keys;
drop table if exists bot_api_keys;

-- =============================================================
-- 4. Drop bots
-- =============================================================
drop policy if exists "bot_owner_all" on bots;
drop table if exists bots;

-- =============================================================
-- 5. Revert KB table RLS (restore to pre-003 state: no RLS)
--    WARNING: This re-opens the security gap from migration 002
-- =============================================================

-- kb_patterns
drop policy if exists "kb_patterns_read" on kb_patterns;
drop policy if exists "kb_patterns_service_write" on kb_patterns;
drop policy if exists "kb_patterns_service_update" on kb_patterns;
drop policy if exists "kb_patterns_service_delete" on kb_patterns;
alter table kb_patterns disable row level security;

-- kb_market_regimes
drop policy if exists "kb_regimes_read" on kb_market_regimes;
drop policy if exists "kb_regimes_service_write" on kb_market_regimes;
drop policy if exists "kb_regimes_service_update" on kb_market_regimes;
drop policy if exists "kb_regimes_service_delete" on kb_market_regimes;
alter table kb_market_regimes disable row level security;

-- kb_lessons_learned
drop policy if exists "kb_lessons_read" on kb_lessons_learned;
drop policy if exists "kb_lessons_service_write" on kb_lessons_learned;
drop policy if exists "kb_lessons_service_update" on kb_lessons_learned;
drop policy if exists "kb_lessons_service_delete" on kb_lessons_learned;
alter table kb_lessons_learned disable row level security;

-- kb_macro_events
drop policy if exists "kb_macro_events_read" on kb_macro_events;
drop policy if exists "kb_macro_events_service_write" on kb_macro_events;
drop policy if exists "kb_macro_events_service_update" on kb_macro_events;
drop policy if exists "kb_macro_events_service_delete" on kb_macro_events;
alter table kb_macro_events disable row level security;

-- kb_correlations
drop policy if exists "kb_correlations_read" on kb_correlations;
drop policy if exists "kb_correlations_service_write" on kb_correlations;
drop policy if exists "kb_correlations_service_update" on kb_correlations;
drop policy if exists "kb_correlations_service_delete" on kb_correlations;
alter table kb_correlations disable row level security;

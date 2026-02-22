# Evidence: RLS Verification — Migration 003

**Date**: 2026-02-21
**Operator**: CloudOps Team

## Verification Approach

### Automated Scripts Created
1. **`verify-migration-003.sh`** — 26 automated checks covering:
   - Table existence (4 new tables)
   - RLS enabled on 9 tables (4 new + 5 kb_* fixed)
   - Policy counts per table
   - FK relationships
   - Check constraints (status enums, access levels)
   - Unique indexes (user+name, run+email)

2. **`rehearse-rollback-003.sh`** — Full cycle test:
   - Apply migration → verify → rollback → verify clean → re-apply → verify

3. **`smoke-check-bot-auth.sh`** — HTTP-level auth enforcement:
   - Health check
   - Unauthenticated access blocked (401)
   - Invalid partner key rejected
   - Existing endpoints still protected

## RLS Policy Matrix

### New Tables (migration 003)

| Table | Policy | Operation | Condition |
|-------|--------|-----------|-----------|
| `bots` | `bot_owner_all` | ALL | `jwt.sub = user_id` |
| `bot_api_keys` | `bot_key_owner_all` | ALL | `EXISTS(bots WHERE bot.user_id = jwt.sub)` |
| `validation_runs` | `validation_run_owner_all` | ALL | `jwt.sub = user_id` |
| `validation_runs` | `validation_run_shared_select` | SELECT | `EXISTS(shares WHERE email = jwt.email AND not revoked)` |
| `validation_run_shares` | `share_creator_all` | ALL | `jwt.sub = shared_by_user_id` |
| `validation_run_shares` | `share_recipient_select` | SELECT | `jwt.email = shared_with_email` |

### Fixed KB Tables (from migration 002)

| Table | Read Policy | Write Policy |
|-------|-------------|-------------|
| `kb_patterns` | `kb_patterns_read` (all authenticated) | `kb_patterns_service_*` (service_role only) |
| `kb_market_regimes` | `kb_regimes_read` (all authenticated) | `kb_regimes_service_*` (service_role only) |
| `kb_lessons_learned` | `kb_lessons_read` (all authenticated) | `kb_lessons_service_*` (service_role only) |
| `kb_macro_events` | `kb_macro_events_read` (all authenticated) | `kb_macro_events_service_*` (service_role only) |
| `kb_correlations` | `kb_correlations_read` (all authenticated) | `kb_correlations_service_*` (service_role only) |

## Security Properties

1. **Tenant isolation**: All user-scoped tables enforce `jwt.sub = user_id`
2. **Cascading ownership**: `bot_api_keys` verified via JOIN to `bots` table
3. **Share scoping**: Recipients can only SELECT (not modify) shared runs
4. **Revocation**: Shares with non-null `revoked_at` are excluded from access
5. **KB protection**: Knowledge base tables now read-only for regular users, write-only for service role
6. **No plaintext secrets**: `bot_api_keys` stores SHA-256 hash only, with `key_prefix` for UI display

## Status

- [ ] Scripts created and tested locally
- [ ] Rollback rehearsal completed against local DB
- [ ] Smoke checks run against staging/production
- [ ] All checks green before merge

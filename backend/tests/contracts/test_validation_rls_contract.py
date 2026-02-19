"""Contract tests for tenant-aware validation RLS policies (#242)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = REPO_ROOT / "supabase" / "migrations" / "004_validation_storage_rls_tenant_scope.sql"


def _migration_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8").lower()


def _between(text: str, start: str, end: str | None) -> str:
    start_idx = text.index(start)
    if end is None:
        return text[start_idx:]
    end_idx = text.index(end, start_idx)
    return text[start_idx:end_idx]


def _run_scope_allows(*, jwt_sub: str, jwt_tenant: str, run_user_id: str, run_tenant_id: str) -> bool:
    return jwt_sub == run_user_id and jwt_tenant == run_tenant_id


def test_tenant_aware_rls_migration_exists() -> None:
    assert MIGRATION_PATH.exists(), f"Missing migration: {MIGRATION_PATH}"


def test_validation_runs_updated_at_trigger_contract_is_present() -> None:
    sql = _migration_sql()
    assert "create or replace function set_validation_runs_updated_at()" in sql
    assert "create trigger trg_validation_runs_updated_at" in sql
    assert "before update on validation_runs" in sql
    assert "if new.updated_at is null or new.updated_at = old.updated_at then" in sql


def test_validation_runs_policy_requires_user_and_tenant_scope() -> None:
    sql = _migration_sql()
    policy = _between(
        sql,
        'create policy "users can manage own validation runs" on validation_runs',
        'drop policy if exists "users can manage own validation review states" on validation_review_states;',
    )
    assert "auth.jwt() ->> 'sub' = user_id" in policy
    assert "auth.jwt() ->> 'tenant_id' = tenant_id" in policy


def test_validation_review_states_policy_requires_parent_run_user_and_tenant_scope() -> None:
    sql = _migration_sql()
    policy = _between(
        sql,
        'create policy "users can manage own validation review states" on validation_review_states',
        'drop policy if exists "users can manage own validation blob refs" on validation_blob_refs;',
    )
    assert "auth.jwt() ->> 'sub' = runs.user_id" in policy
    assert "auth.jwt() ->> 'tenant_id' = runs.tenant_id" in policy


def test_validation_blob_refs_policy_requires_parent_run_user_and_tenant_scope() -> None:
    sql = _migration_sql()
    policy = _between(
        sql,
        'create policy "users can manage own validation blob refs" on validation_blob_refs',
        'drop policy if exists "users can manage own validation baselines" on validation_baselines;',
    )
    assert "auth.jwt() ->> 'sub' = runs.user_id" in policy
    assert "auth.jwt() ->> 'tenant_id' = runs.tenant_id" in policy


def test_validation_baselines_policy_requires_user_and_tenant_scope() -> None:
    sql = _migration_sql()
    policy = _between(
        sql,
        'create policy "users can manage own validation baselines" on validation_baselines',
        None,
    )
    assert "auth.jwt() ->> 'sub' = user_id" in policy
    assert "auth.jwt() ->> 'tenant_id' = tenant_id" in policy


def test_cross_tenant_access_is_denied_by_policy_contract() -> None:
    assert _run_scope_allows(
        jwt_sub="user-001",
        jwt_tenant="tenant-001",
        run_user_id="user-001",
        run_tenant_id="tenant-001",
    )
    assert not _run_scope_allows(
        jwt_sub="user-001",
        jwt_tenant="tenant-002",
        run_user_id="user-001",
        run_tenant_id="tenant-001",
    )
    assert not _run_scope_allows(
        jwt_sub="user-002",
        jwt_tenant="tenant-001",
        run_user_id="user-001",
        run_tenant_id="tenant-001",
    )

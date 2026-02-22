"""Contract checks for validation identity + run-sharing storage migration."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = REPO_ROOT / "supabase" / "migrations" / "006_validation_identity_and_sharing.sql"


def _migration_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8").lower()


def _between(text: str, start: str, end: str | None) -> str:
    start_idx = text.index(start)
    if end is None:
        return text[start_idx:]
    end_idx = text.index(end, start_idx)
    return text[start_idx:end_idx]


def test_validation_identity_sharing_migration_exists() -> None:
    assert MIGRATION_PATH.exists(), f"Missing migration: {MIGRATION_PATH}"


def test_validation_runs_actor_columns_are_declared() -> None:
    sql = _migration_sql()
    assert "add column if not exists owner_user_id text" in sql
    assert "add column if not exists actor_type text" in sql
    assert "add column if not exists actor_id text" in sql
    assert "check (actor_type in ('user', 'bot'))" in sql


def test_validation_run_share_invites_table_contract_fields_exist() -> None:
    sql = _migration_sql()
    table_block = _between(
        sql,
        "create table if not exists validation_run_share_invites",
        "create index if not exists idx_validation_run_share_invites_run",
    )
    for token in (
        "invite_id text primary key",
        "run_id text not null references validation_runs(run_id)",
        "tenant_id text not null",
        "owner_user_id text not null",
        "invitee_email text not null",
        "permission text not null check (permission in ('view', 'review'))",
        "status text not null check (status in ('pending', 'accepted', 'revoked'))",
        "accepted_user_id text",
    ):
        assert token in table_block


def test_validation_run_share_access_table_contract_fields_exist() -> None:
    sql = _migration_sql()
    table_block = _between(
        sql,
        "create table if not exists validation_run_share_access",
        "create index if not exists idx_validation_run_share_access_user",
    )
    for token in (
        "run_id text not null references validation_runs(run_id)",
        "tenant_id text not null",
        "owner_user_id text not null",
        "user_id text not null",
        "permission text not null check (permission in ('view', 'review'))",
        "primary key (run_id, user_id)",
    ):
        assert token in table_block


def test_validation_run_share_policies_require_owner_and_tenant_scope() -> None:
    sql = _migration_sql()
    owner_policy = _between(
        sql,
        'create policy "owners can manage validation run share invites" on validation_run_share_invites',
        'drop policy if exists "owners can manage shared validation access" on validation_run_share_access;',
    )
    assert "auth.jwt() ->> 'sub' = owner_user_id" in owner_policy
    assert "auth.jwt() ->> 'tenant_id' = tenant_id" in owner_policy

    shared_access_policy = _between(
        sql,
        'create policy "users can read own shared validation access" on validation_run_share_access',
        None,
    )
    assert "auth.jwt() ->> 'sub' = user_id" in shared_access_policy
    assert "auth.jwt() ->> 'tenant_id' = tenant_id" in shared_access_policy

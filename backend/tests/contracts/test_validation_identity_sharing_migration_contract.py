"""Contract checks for validation identity/sharing migration invariants (#311)."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = REPO_ROOT / "supabase" / "migrations" / "006_validation_identity_sharing_v2.sql"


def _migration_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8").lower()


def _between(text: str, start: str, end: str | None) -> str:
    start_idx = text.index(start)
    if end is None:
        return text[start_idx:]
    end_idx = text.index(end, start_idx)
    return text[start_idx:end_idx]


def test_identity_sharing_migration_exists() -> None:
    assert MIGRATION_PATH.exists(), f"Missing migration: {MIGRATION_PATH}"


def test_bots_updated_at_trigger_contract_is_present() -> None:
    sql = _migration_sql()
    assert "create or replace function set_bots_updated_at()" in sql
    assert "create trigger trg_bots_updated_at" in sql
    assert "before update on bots" in sql
    assert "if new.updated_at is null or new.updated_at = old.updated_at then" in sql


def test_validation_invites_has_owner_and_recipient_policies() -> None:
    sql = _migration_sql()
    owner_policy = _between(
        sql,
        'create policy "users can manage own validation invites" on validation_invites',
        'drop policy if exists "invite recipients can read validation invites" on validation_invites;',
    )
    assert "auth.jwt() ->> 'sub' = owner_user_id" in owner_policy
    assert "auth.jwt() ->> 'tenant_id' = tenant_id" in owner_policy

    recipient_policy = _between(
        sql,
        'create policy "invite recipients can read validation invites" on validation_invites',
        'drop policy if exists "users can manage own validation run shares" on validation_run_shares;',
    )
    assert "for select" in recipient_policy
    assert "lower(coalesce(auth.jwt() ->> 'email', '')) = lower(invited_email)" in recipient_policy
    assert "accepted_by_user_id is not null" in recipient_policy
    assert "auth.jwt() ->> 'sub' = accepted_by_user_id" in recipient_policy
    assert "auth.jwt() ->> 'tenant_id' = tenant_id" in recipient_policy

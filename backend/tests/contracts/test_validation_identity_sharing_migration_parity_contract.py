"""Parity checks for canonical validation identity + sharing migrations."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"
BRIDGE_003 = MIGRATIONS_DIR / "003_validation_storage_bridge_run_id.sql"
CANONICAL_006 = MIGRATIONS_DIR / "006_validation_identity_sharing_v2.sql"
FORWARD_007 = MIGRATIONS_DIR / "007_validation_identity_actor_runtime_parity.sql"
FORWARD_008 = MIGRATIONS_DIR / "008_validation_schema_lineage_reconciliation.sql"


def _read_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_identity_sharing_uses_single_canonical_006_migration() -> None:
    identity_006_files = sorted(path.name for path in MIGRATIONS_DIR.glob("006_validation_identity*.sql"))
    assert identity_006_files == ["006_validation_identity_sharing_v2.sql"]


def test_runtime_actor_parity_forward_migration_exists() -> None:
    assert FORWARD_007.exists(), f"Missing migration: {FORWARD_007}"


def test_legacy_run_id_bridge_exists_for_003_lineage_conflict() -> None:
    assert BRIDGE_003.exists(), f"Missing migration: {BRIDGE_003}"
    sql = _read_sql(BRIDGE_003)
    for token in (
        "add column if not exists run_id text",
        "set run_id = coalesce(run_id, id::text)",
        "idx_validation_runs_run_id_unique",
    ):
        assert token in sql


def test_validation_lineage_reconciliation_forward_migration_exists() -> None:
    assert FORWARD_008.exists(), f"Missing migration: {FORWARD_008}"


def test_validation_identity_table_family_drift_is_prevented() -> None:
    combined = "\n".join(_read_sql(path) for path in sorted(MIGRATIONS_DIR.glob("*.sql")))
    assert "create table if not exists validation_invites" in combined
    assert "create table if not exists validation_run_shares" in combined
    assert "create table if not exists validation_run_share_invites" not in combined
    assert "create table if not exists validation_run_share_access" not in combined


def test_forward_actor_parity_migration_adds_runtime_actor_columns() -> None:
    sql = _read_sql(FORWARD_007)
    for token in (
        "add column if not exists actor_type text",
        "add column if not exists actor_id text",
        "coalesce(actor_type, owner_actor_type, 'user')",
        "coalesce(actor_id, owner_actor_id, user_id)",
        "check (actor_type in ('user', 'bot'))",
        "idx_validation_runs_actor",
        "idx_validation_runs_owner_tenant_created",
    ):
        assert token in sql


def test_forward_lineage_reconciliation_migration_normalizes_run_and_share_shapes() -> None:
    sql = _read_sql(FORWARD_008)
    for token in (
        "add column if not exists run_id text",
        "set run_id = coalesce(run_id, id::text)",
        "idx_validation_runs_run_id_unique",
        "alter column run_id type text using run_id::text",
        "add column if not exists owner_user_id text",
        "add column if not exists owner_actor_type text",
        "add column if not exists owner_actor_id text",
        "add column if not exists actor_type text",
        "add column if not exists actor_id text",
        "create policy \"users can manage own validation run shares\"",
        "create policy \"users can read shared validation runs\"",
    ):
        assert token in sql


def test_canonical_006_contract_is_still_present() -> None:
    sql = _read_sql(CANONICAL_006)
    assert "create table if not exists validation_invites" in sql
    assert "create table if not exists validation_run_shares" in sql

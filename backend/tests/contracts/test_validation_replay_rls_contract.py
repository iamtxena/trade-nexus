"""Contract checks for replay persistence + tenant-aware RLS policy (#229)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = REPO_ROOT / "supabase" / "migrations" / "005_validation_replays_tenant_scope.sql"


def _migration_sql() -> str:
    return MIGRATION_PATH.read_text(encoding="utf-8").lower()


def _between(text: str, start: str, end: str | None) -> str:
    start_idx = text.index(start)
    if end is None:
        return text[start_idx:]
    end_idx = text.index(end, start_idx)
    return text[start_idx:end_idx]


def test_validation_replay_migration_exists() -> None:
    assert MIGRATION_PATH.exists(), f"Missing migration: {MIGRATION_PATH}"


def test_validation_replay_table_contract_fields_exist() -> None:
    sql = _migration_sql()
    table_block = _between(sql, "create table if not exists validation_replays", "create index if not exists idx_validation_replays_tenant_user_created")

    required_tokens = (
        "replay_id text primary key",
        "baseline_id text not null references validation_baselines(id)",
        "baseline_run_id text not null references validation_runs(run_id)",
        "candidate_run_id text not null references validation_runs(run_id)",
        "tenant_id text not null",
        "user_id text not null",
        "decision text not null check (decision in ('pass', 'conditional_pass', 'fail', 'unknown'))",
        "merge_blocked boolean not null",
        "release_blocked boolean not null",
        "merge_gate_status text not null check (merge_gate_status in ('pass', 'blocked'))",
        "release_gate_status text not null check (release_gate_status in ('pass', 'blocked'))",
        "baseline_decision text not null",
        "candidate_decision text not null",
        "metric_drift_delta_pct double precision not null check (metric_drift_delta_pct >= 0)",
        "metric_drift_threshold_pct double precision not null check (metric_drift_threshold_pct >= 0)",
        "threshold_breached boolean not null",
        "reasons jsonb not null default '[]'::jsonb",
    )
    for token in required_tokens:
        assert token in table_block


def test_validation_replay_policy_requires_user_and_tenant_scope() -> None:
    sql = _migration_sql()
    policy = _between(
        sql,
        'create policy "users can manage own validation replays" on validation_replays',
        None,
    )
    assert "auth.jwt() ->> 'sub' = user_id" in policy
    assert "auth.jwt() ->> 'tenant_id' = tenant_id" in policy

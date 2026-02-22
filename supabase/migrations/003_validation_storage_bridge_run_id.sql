-- Forward compatibility bridge for conflicting 003 validation_runs lineage.
--
-- Purpose:
-- - Keep forward migration execution viable when `validation_runs` was created with
--   legacy `id uuid` shape before the canonical `run_id text` lineage.
-- - Prepare `validation_runs(run_id)` so downstream 003 schema migrations can safely
--   create run_id-based foreign keys.
--
-- Rollback (manual):
-- 1) drop index if exists idx_validation_runs_run_id_unique;
-- 2) alter table validation_runs drop column if exists run_id;

alter table if exists validation_runs
  add column if not exists run_id text;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'validation_runs'
      and column_name = 'id'
  ) then
    execute $update$
      update validation_runs
      set run_id = coalesce(run_id, id::text)
      where run_id is null
    $update$;
  end if;

  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'validation_runs'
      and column_name = 'run_id'
  ) then
    execute $update$
      update validation_runs
      set run_id = coalesce(run_id, gen_random_uuid()::text)
      where run_id is null
    $update$;
  end if;
end;
$$;

create unique index if not exists idx_validation_runs_run_id_unique
  on validation_runs (run_id);

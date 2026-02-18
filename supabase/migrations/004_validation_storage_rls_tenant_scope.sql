-- GateV4 follow-up (#242): tenant-aware RLS hardening for validation storage tables.
-- JWT claims contract: auth.jwt() ->> 'sub' maps to user_id, auth.jwt() ->> 'tenant_id' maps to tenant_id.

create or replace function set_validation_runs_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_validation_runs_updated_at on validation_runs;
create trigger trg_validation_runs_updated_at
  before update on validation_runs
  for each row
  execute function set_validation_runs_updated_at();

drop policy if exists "Users can manage own validation runs" on validation_runs;
create policy "Users can manage own validation runs" on validation_runs
  for all
  using (
    auth.jwt() ->> 'sub' = user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  )
  with check (
    auth.jwt() ->> 'sub' = user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

drop policy if exists "Users can manage own validation review states" on validation_review_states;
create policy "Users can manage own validation review states" on validation_review_states
  for all
  using (
    exists (
      select 1
      from validation_runs runs
      where runs.run_id = validation_review_states.run_id
        and auth.jwt() ->> 'sub' = runs.user_id
        and auth.jwt() ->> 'tenant_id' = runs.tenant_id
    )
  )
  with check (
    exists (
      select 1
      from validation_runs runs
      where runs.run_id = validation_review_states.run_id
        and auth.jwt() ->> 'sub' = runs.user_id
        and auth.jwt() ->> 'tenant_id' = runs.tenant_id
    )
  );

drop policy if exists "Users can manage own validation blob refs" on validation_blob_refs;
create policy "Users can manage own validation blob refs" on validation_blob_refs
  for all
  using (
    exists (
      select 1
      from validation_runs runs
      where runs.run_id = validation_blob_refs.run_id
        and auth.jwt() ->> 'sub' = runs.user_id
        and auth.jwt() ->> 'tenant_id' = runs.tenant_id
    )
  )
  with check (
    exists (
      select 1
      from validation_runs runs
      where runs.run_id = validation_blob_refs.run_id
        and auth.jwt() ->> 'sub' = runs.user_id
        and auth.jwt() ->> 'tenant_id' = runs.tenant_id
    )
  );

drop policy if exists "Users can manage own validation baselines" on validation_baselines;
create policy "Users can manage own validation baselines" on validation_baselines
  for all
  using (
    auth.jwt() ->> 'sub' = user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  )
  with check (
    auth.jwt() ->> 'sub' = user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

-- Validation schema lineage reconciliation (forward-only).
--
-- Purpose:
-- - Normalize `validation_runs` / `validation_run_shares` across legacy histories.
-- - Preserve canonical run identity as `validation_runs.run_id` (text).
-- - Keep canonical owner actor columns and runtime actor mirror columns aligned.
--
-- Rollback (manual, last resort):
-- 1) drop index if exists idx_validation_runs_run_id_unique;
-- 2) drop index if exists idx_validation_runs_owner_actor;
-- 3) drop index if exists idx_validation_runs_owner_user;
-- 4) drop index if exists idx_validation_runs_actor;
-- 5) drop index if exists idx_validation_run_shares_run_created;
-- 6) drop index if exists idx_validation_run_shares_owner_scope;
-- 7) drop index if exists idx_validation_run_shares_shared_user;
-- 8) drop index if exists idx_validation_run_shares_active_email;
-- 9) restore prior constraints/policies only via approved repair migration.

alter table if exists validation_runs
  add column if not exists run_id text,
  add column if not exists request_id text,
  add column if not exists tenant_id text,
  add column if not exists profile text,
  add column if not exists final_decision text,
  add column if not exists artifact_type text,
  add column if not exists artifact_schema_version text,
  add column if not exists artifact_ref text,
  add column if not exists updated_at timestamptz default now(),
  add column if not exists owner_user_id text,
  add column if not exists owner_actor_type text,
  add column if not exists owner_actor_id text,
  add column if not exists owner_actor_metadata jsonb default '{}'::jsonb,
  add column if not exists owner_bot_id uuid,
  add column if not exists actor_type text,
  add column if not exists actor_id text;

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
end;
$$;

update validation_runs
set run_id = coalesce(run_id, gen_random_uuid()::text)
where run_id is null;

update validation_runs
set request_id = coalesce(nullif(btrim(request_id), ''), 'legacy-' || run_id)
where request_id is null or btrim(request_id) = '';

update validation_runs
set tenant_id = coalesce(nullif(btrim(tenant_id), ''), 'legacy')
where tenant_id is null or btrim(tenant_id) = '';

update validation_runs
set profile = case upper(coalesce(profile, 'STANDARD'))
  when 'FAST' then 'FAST'
  when 'STANDARD' then 'STANDARD'
  when 'EXPERT' then 'EXPERT'
  else 'STANDARD'
end;

alter table if exists validation_runs drop constraint if exists validation_runs_status_check;
alter table if exists validation_runs drop constraint if exists chk_validation_runs_status;

update validation_runs
set status = case lower(coalesce(status, 'queued'))
  when 'queued' then 'queued'
  when 'running' then 'running'
  when 'completed' then 'completed'
  when 'failed' then 'failed'
  when 'pending' then 'queued'
  when 'passed' then 'completed'
  when 'error' then 'failed'
  when 'cancelled' then 'failed'
  else 'queued'
end;

update validation_runs
set final_decision = case lower(coalesce(final_decision, 'pending'))
  when 'pending' then 'pending'
  when 'pass' then 'pass'
  when 'conditional_pass' then 'conditional_pass'
  when 'fail' then 'fail'
  else 'pending'
end;

update validation_runs
set artifact_type = case lower(coalesce(artifact_type, 'validation_run'))
  when 'validation_run' then 'validation_run'
  when 'validation_llm_snapshot' then 'validation_llm_snapshot'
  else 'validation_run'
end;

update validation_runs
set artifact_schema_version = coalesce(nullif(btrim(artifact_schema_version), ''), 'validation-run.v1')
where artifact_schema_version is null or btrim(artifact_schema_version) = '';

update validation_runs
set artifact_ref = coalesce(nullif(btrim(artifact_ref), ''), 'blob://validation/' || run_id || '/validation-run.json')
where artifact_ref is null or btrim(artifact_ref) = '';

update validation_runs
set created_at = coalesce(created_at, now())
where created_at is null;

update validation_runs
set updated_at = coalesce(updated_at, created_at, now())
where updated_at is null;

update validation_runs
set owner_user_id = coalesce(owner_user_id, user_id)
where owner_user_id is null;

update validation_runs
set owner_actor_type = case lower(coalesce(owner_actor_type, actor_type, 'user'))
  when 'bot' then 'bot'
  else 'user'
end;

update validation_runs
set owner_actor_id = coalesce(nullif(btrim(owner_actor_id), ''), nullif(btrim(actor_id), ''), owner_user_id)
where owner_actor_id is null or btrim(owner_actor_id) = '';

update validation_runs
set owner_actor_metadata = coalesce(owner_actor_metadata, '{}'::jsonb)
where owner_actor_metadata is null;

update validation_runs
set owner_actor_metadata = owner_actor_metadata || jsonb_build_object('ownerUserId', owner_user_id);

update validation_runs
set actor_type = case lower(coalesce(actor_type, owner_actor_type, 'user'))
  when 'bot' then 'bot'
  else 'user'
end;

update validation_runs
set actor_id = coalesce(nullif(btrim(actor_id), ''), nullif(btrim(owner_actor_id), ''), owner_user_id)
where actor_id is null or btrim(actor_id) = '';

alter table if exists validation_runs drop constraint if exists chk_validation_runs_profile;
alter table if exists validation_runs drop constraint if exists chk_validation_runs_final_decision;
alter table if exists validation_runs drop constraint if exists chk_validation_runs_artifact_type;
alter table if exists validation_runs drop constraint if exists chk_validation_runs_owner_actor_type;
alter table if exists validation_runs drop constraint if exists chk_validation_runs_actor_type;

alter table validation_runs
  add constraint chk_validation_runs_profile
    check (profile in ('FAST', 'STANDARD', 'EXPERT')),
  add constraint chk_validation_runs_status
    check (status in ('queued', 'running', 'completed', 'failed')),
  add constraint chk_validation_runs_final_decision
    check (final_decision in ('pending', 'pass', 'conditional_pass', 'fail')),
  add constraint chk_validation_runs_artifact_type
    check (artifact_type in ('validation_run', 'validation_llm_snapshot')),
  add constraint chk_validation_runs_owner_actor_type
    check (owner_actor_type in ('user', 'bot')),
  add constraint chk_validation_runs_actor_type
    check (actor_type in ('user', 'bot'));

alter table validation_runs
  alter column run_id set not null,
  alter column request_id set not null,
  alter column tenant_id set not null,
  alter column user_id set not null,
  alter column profile set not null,
  alter column status set not null,
  alter column final_decision set not null,
  alter column artifact_type set not null,
  alter column artifact_schema_version set not null,
  alter column artifact_ref set not null,
  alter column created_at set not null,
  alter column updated_at set not null,
  alter column owner_user_id set not null,
  alter column owner_actor_type set not null,
  alter column owner_actor_id set not null,
  alter column owner_actor_metadata set not null,
  alter column actor_type set not null,
  alter column actor_id set not null;

alter table validation_runs
  alter column request_id set default 'legacy-reconciled',
  alter column tenant_id set default 'legacy',
  alter column profile set default 'STANDARD',
  alter column status set default 'queued',
  alter column final_decision set default 'pending',
  alter column artifact_type set default 'validation_run',
  alter column artifact_schema_version set default 'validation-run.v1',
  alter column artifact_ref set default 'blob://validation/reconciled/validation-run.json',
  alter column updated_at set default now(),
  alter column owner_actor_metadata set default '{}'::jsonb,
  alter column owner_actor_type set default 'user',
  alter column actor_type set default 'user';

create unique index if not exists idx_validation_runs_run_id_unique
  on validation_runs (run_id);

create index if not exists idx_validation_runs_owner_actor
  on validation_runs (tenant_id, owner_actor_type, owner_actor_id, created_at desc);

create index if not exists idx_validation_runs_owner_user
  on validation_runs (tenant_id, owner_user_id, created_at desc);

create index if not exists idx_validation_runs_actor
  on validation_runs (tenant_id, actor_type, actor_id, created_at desc);

create table if not exists validation_run_shares (
  id uuid primary key default gen_random_uuid(),
  run_id text not null,
  tenant_id text not null,
  owner_user_id text not null,
  shared_with_email text not null,
  shared_with_user_id text,
  invite_id uuid,
  status text not null default 'active'
    check (status in ('active', 'revoked')),
  metadata jsonb not null default '{}'::jsonb,
  granted_at timestamptz not null default now(),
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);

do $$
declare
  fk_constraint record;
begin
  if to_regclass('public.validation_run_shares') is not null then
    for fk_constraint in
      select conname
      from pg_constraint
      where conrelid = 'public.validation_run_shares'::regclass
        and contype = 'f'
    loop
      execute format('alter table validation_run_shares drop constraint if exists %I', fk_constraint.conname);
    end loop;
  end if;
end;
$$;

do $$
declare
  run_id_type text;
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'validation_run_shares'
      and column_name = 'run_id'
  ) then
    select data_type
    into run_id_type
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'validation_run_shares'
      and column_name = 'run_id';

    if run_id_type = 'uuid' then
      execute 'alter table validation_run_shares alter column run_id type text using run_id::text';
    end if;
  end if;
end;
$$;

alter table if exists validation_run_shares
  add column if not exists tenant_id text,
  add column if not exists owner_user_id text,
  add column if not exists shared_with_email text,
  add column if not exists shared_with_user_id text,
  add column if not exists invite_id uuid,
  add column if not exists status text,
  add column if not exists metadata jsonb default '{}'::jsonb,
  add column if not exists granted_at timestamptz,
  add column if not exists revoked_at timestamptz,
  add column if not exists created_at timestamptz default now();

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'validation_run_shares'
      and column_name = 'shared_by_user_id'
  ) then
    execute $update$
      update validation_run_shares
      set owner_user_id = coalesce(owner_user_id, shared_by_user_id)
      where owner_user_id is null
    $update$;
  end if;
end;
$$;

update validation_run_shares shares
set tenant_id = runs.tenant_id,
    owner_user_id = coalesce(shares.owner_user_id, runs.owner_user_id, runs.user_id)
from validation_runs runs
where shares.run_id = runs.run_id
  and (shares.tenant_id is null or shares.owner_user_id is null);

update validation_run_shares
set tenant_id = coalesce(nullif(btrim(tenant_id), ''), 'legacy')
where tenant_id is null or btrim(tenant_id) = '';

update validation_run_shares
set owner_user_id = coalesce(nullif(btrim(owner_user_id), ''), 'legacy-owner')
where owner_user_id is null or btrim(owner_user_id) = '';

update validation_run_shares
set shared_with_email = coalesce(nullif(btrim(shared_with_email), ''), 'unknown@example.invalid')
where shared_with_email is null or btrim(shared_with_email) = '';

update validation_run_shares
set status = case lower(coalesce(status, 'active'))
  when 'revoked' then 'revoked'
  when 'active' then 'active'
  else case when revoked_at is not null then 'revoked' else 'active' end
end;

update validation_run_shares
set metadata = coalesce(metadata, '{}'::jsonb)
where metadata is null;

update validation_run_shares
set created_at = coalesce(created_at, now())
where created_at is null;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'validation_run_shares'
      and column_name = 'accepted_at'
  ) then
    execute $update$
      update validation_run_shares
      set granted_at = coalesce(granted_at, accepted_at, created_at, now())
      where granted_at is null
    $update$;
  else
    update validation_run_shares
    set granted_at = coalesce(granted_at, created_at, now())
    where granted_at is null;
  end if;
end;
$$;

alter table if exists validation_run_shares drop constraint if exists validation_run_shares_status_check;
alter table if exists validation_run_shares drop constraint if exists chk_validation_run_shares_status;

alter table validation_run_shares
  add constraint chk_validation_run_shares_status
  check (status in ('active', 'revoked'));

alter table validation_run_shares
  alter column run_id set not null,
  alter column tenant_id set not null,
  alter column owner_user_id set not null,
  alter column shared_with_email set not null,
  alter column status set not null,
  alter column metadata set not null,
  alter column granted_at set not null,
  alter column created_at set not null;

alter table validation_run_shares
  alter column status set default 'active',
  alter column metadata set default '{}'::jsonb,
  alter column granted_at set default now(),
  alter column created_at set default now();

create index if not exists idx_validation_run_shares_run_created
  on validation_run_shares (run_id, created_at desc);

create index if not exists idx_validation_run_shares_owner_scope
  on validation_run_shares (tenant_id, owner_user_id, created_at desc);

create index if not exists idx_validation_run_shares_shared_user
  on validation_run_shares (shared_with_user_id, created_at desc);

create unique index if not exists idx_validation_run_shares_active_email
  on validation_run_shares (run_id, lower(shared_with_email))
  where status = 'active';

alter table validation_run_shares enable row level security;

drop policy if exists "share_creator_all" on validation_run_shares;
drop policy if exists "share_recipient_select" on validation_run_shares;
drop policy if exists "Users can manage own validation run shares" on validation_run_shares;
drop policy if exists "Users can read shared validation runs" on validation_run_shares;

create policy "Users can manage own validation run shares" on validation_run_shares
  for all
  using (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  )
  with check (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

create policy "Users can read shared validation runs" on validation_run_shares
  for select
  using (
    shared_with_user_id is not null
    and auth.jwt() ->> 'sub' = shared_with_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

-- Re-bind optional foreign keys only when target tables exist.
do $$
begin
  if to_regclass('public.bots') is not null then
    alter table validation_runs
      drop constraint if exists validation_runs_owner_bot_id_fkey;
    alter table validation_runs
      add constraint validation_runs_owner_bot_id_fkey
      foreign key (owner_bot_id) references bots(id) on delete set null;
  end if;

  if to_regclass('public.validation_invites') is not null then
    alter table validation_run_shares
      drop constraint if exists validation_run_shares_invite_id_fkey;
    alter table validation_run_shares
      add constraint validation_run_shares_invite_id_fkey
      foreign key (invite_id) references validation_invites(id) on delete set null;
  end if;
end;
$$;

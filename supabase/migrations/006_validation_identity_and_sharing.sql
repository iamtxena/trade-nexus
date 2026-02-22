-- Validation Identity + Sharing Program v2
-- Adds actor metadata to validation_runs and run-level sharing tables.

alter table validation_runs
  add column if not exists owner_user_id text;

update validation_runs
set owner_user_id = user_id
where owner_user_id is null;

alter table validation_runs
  alter column owner_user_id set not null;

alter table validation_runs
  add column if not exists actor_type text;

update validation_runs
set actor_type = 'user'
where actor_type is null;

alter table validation_runs
  alter column actor_type set not null;

alter table validation_runs
  drop constraint if exists chk_validation_runs_actor_type;

alter table validation_runs
  add constraint chk_validation_runs_actor_type
  check (actor_type in ('user', 'bot'));

alter table validation_runs
  add column if not exists actor_id text;

update validation_runs
set actor_id = user_id
where actor_id is null;

alter table validation_runs
  alter column actor_id set not null;

create index if not exists idx_validation_runs_owner_tenant_created
  on validation_runs (tenant_id, owner_user_id, created_at desc);

create index if not exists idx_validation_runs_actor
  on validation_runs (tenant_id, actor_type, actor_id, created_at desc);

create table if not exists validation_run_share_invites (
  invite_id text primary key,
  run_id text not null references validation_runs(run_id) on delete cascade,
  tenant_id text not null,
  owner_user_id text not null,
  invitee_email text not null,
  permission text not null check (permission in ('view', 'review')),
  status text not null check (status in ('pending', 'accepted', 'revoked')),
  accepted_user_id text,
  created_at timestamptz not null default now(),
  accepted_at timestamptz
);

create index if not exists idx_validation_run_share_invites_run
  on validation_run_share_invites (run_id, created_at desc);

create index if not exists idx_validation_run_share_invites_email
  on validation_run_share_invites (tenant_id, invitee_email, status, created_at desc);

create table if not exists validation_run_share_access (
  run_id text not null references validation_runs(run_id) on delete cascade,
  tenant_id text not null,
  owner_user_id text not null,
  user_id text not null,
  permission text not null check (permission in ('view', 'review')),
  granted_at timestamptz not null default now(),
  primary key (run_id, user_id)
);

create index if not exists idx_validation_run_share_access_user
  on validation_run_share_access (tenant_id, user_id, granted_at desc);

alter table validation_run_share_invites enable row level security;
alter table validation_run_share_access enable row level security;

drop policy if exists "Owners can manage validation run share invites" on validation_run_share_invites;
create policy "Owners can manage validation run share invites" on validation_run_share_invites
  for all
  using (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  )
  with check (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

drop policy if exists "Owners can manage shared validation access" on validation_run_share_access;
create policy "Owners can manage shared validation access" on validation_run_share_access
  for all
  using (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  )
  with check (
    auth.jwt() ->> 'sub' = owner_user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

drop policy if exists "Users can read own shared validation access" on validation_run_share_access;
create policy "Users can read own shared validation access" on validation_run_share_access
  for select
  using (
    auth.jwt() ->> 'sub' = user_id
    and auth.jwt() ->> 'tenant_id' = tenant_id
  );

-- Validation identity runtime parity follow-up
-- Aligns runtime metadata column family with canonical 006 owner_actor_* schema.

alter table if exists validation_runs
  add column if not exists actor_type text,
  add column if not exists actor_id text;

update validation_runs
set actor_type = coalesce(actor_type, owner_actor_type, 'user')
where actor_type is null;

update validation_runs
set actor_id = coalesce(actor_id, owner_actor_id, user_id)
where actor_id is null;

alter table validation_runs
  alter column actor_type set not null;

alter table validation_runs
  alter column actor_id set not null;

alter table validation_runs
  drop constraint if exists chk_validation_runs_actor_type;

alter table validation_runs
  add constraint chk_validation_runs_actor_type
  check (actor_type in ('user', 'bot'));

create index if not exists idx_validation_runs_owner_tenant_created
  on validation_runs (tenant_id, owner_user_id, created_at desc);

create index if not exists idx_validation_runs_actor
  on validation_runs (tenant_id, actor_type, actor_id, created_at desc);

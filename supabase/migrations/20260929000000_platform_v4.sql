-- SSRI Version 4 platform schema.
-- Apply with the Supabase CLI or SQL editor. Do not put the service-role key in the frontend.
-- Admin role is granted only by a privileged SQL update, never by the client.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  display_name text,
  role text not null default 'user' check (role in ('user', 'admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.datasets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  name text not null,
  description text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.dataset_versions (
  id uuid primary key default gen_random_uuid(),
  dataset_id uuid not null references public.datasets (id) on delete cascade,
  version integer not null check (version > 0),
  storage_path text not null,
  file_name text not null,
  file_size bigint not null default 0 check (file_size >= 0),
  content_sha256 text,
  crs text,
  width integer,
  height integer,
  channel_count integer,
  resolution_m double precision,
  validation_status text not null default 'pending'
    check (validation_status in ('pending', 'passed', 'failed')),
  validation_errors jsonb not null default '[]'::jsonb,
  preview jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (dataset_id, version)
);

create table if not exists public.training_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  dataset_id uuid not null references public.datasets (id) on delete cascade,
  dataset_version_id uuid not null references public.dataset_versions (id),
  name text not null,
  description text not null default '',
  status text not null default 'QUEUED'
    check (status in (
      'QUEUED', 'PREPARING', 'VALIDATING', 'TRAINING', 'EVALUATING',
      'COMPLETED', 'FAILED', 'CANCELLED'
    )),
  job_id text,
  error_message text,
  metrics jsonb not null default '{}'::jsonb,
  scientific_validation_status text not null default 'NOT_VALIDATED',
  idempotency_key text,
  seed integer not null default 42,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz
);

create unique index if not exists training_runs_user_idempotency_idx
  on public.training_runs (user_id, idempotency_key)
  where idempotency_key is not null;

create table if not exists public.models (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  training_run_id uuid not null unique references public.training_runs (id) on delete cascade,
  dataset_id uuid not null references public.datasets (id),
  dataset_version_id uuid not null references public.dataset_versions (id),
  version integer not null check (version > 0),
  name text not null,
  checkpoint_path text not null,
  metrics jsonb not null default '{}'::jsonb,
  feature_channels integer not null default 13,
  scientific_validation_status text not null default 'NOT_VALIDATED',
  created_at timestamptz not null default now()
);

create table if not exists public.activities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  action text not null,
  resource_type text not null,
  resource_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists datasets_user_id_idx on public.datasets (user_id, created_at desc);
create index if not exists dataset_versions_dataset_id_idx on public.dataset_versions (dataset_id, version desc);
create index if not exists training_runs_user_id_idx on public.training_runs (user_id, created_at desc);
create index if not exists training_runs_status_idx on public.training_runs (status);
create index if not exists models_user_id_idx on public.models (user_id, created_at desc);
create index if not exists models_training_run_id_idx on public.models (training_run_id);
create index if not exists activities_user_created_idx on public.activities (user_id, created_at desc);
create index if not exists activities_created_idx on public.activities (created_at desc);

create or replace function public.is_platform_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name)
  values (
    new.id,
    coalesce(new.email, ''),
    coalesce(new.raw_user_meta_data ->> 'display_name', split_part(coalesce(new.email, ''), '@', 1))
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

alter table public.profiles enable row level security;
alter table public.datasets enable row level security;
alter table public.dataset_versions enable row level security;
alter table public.training_runs enable row level security;
alter table public.models enable row level security;
alter table public.activities enable row level security;

create policy profiles_select_own on public.profiles
  for select using (id = auth.uid() or public.is_platform_admin());
create policy profiles_update_own on public.profiles
  for update using (id = auth.uid())
  with check (
    id = auth.uid()
    and role = (select p.role from public.profiles p where p.id = auth.uid())
  );

create policy datasets_own on public.datasets
  for all using (user_id = auth.uid() or public.is_platform_admin())
  with check (user_id = auth.uid());

create policy dataset_versions_own on public.dataset_versions
  for all using (
    exists (
      select 1 from public.datasets d
      where d.id = dataset_id and (d.user_id = auth.uid() or public.is_platform_admin())
    )
  )
  with check (
    exists (
      select 1 from public.datasets d
      where d.id = dataset_id and d.user_id = auth.uid()
    )
  );

create policy training_runs_own on public.training_runs
  for all using (user_id = auth.uid() or public.is_platform_admin())
  with check (user_id = auth.uid());

create policy models_own on public.models
  for all using (user_id = auth.uid() or public.is_platform_admin())
  with check (user_id = auth.uid());

create policy activities_select_own on public.activities
  for select using (user_id = auth.uid() or public.is_platform_admin());
create policy activities_insert_own on public.activities
  for insert with check (user_id = auth.uid());

-- Private dataset bucket. Object path: {user_id}/{dataset_id}/{version_id}/{filename}
insert into storage.buckets (id, name, public)
values ('datasets', 'datasets', false)
on conflict (id) do nothing;

create policy dataset_objects_own on storage.objects
  for all using (
    bucket_id = 'datasets'
    and (storage.foldername(name))[1] = auth.uid()::text
  )
  with check (
    bucket_id = 'datasets'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- Cohort Firewall run log. Stores hashes and results only, never raw uploaded data.
create table if not exists public.runs (
  id              uuid primary key default gen_random_uuid(),
  created_at      timestamptz not null default now(),
  cert_id         text not null unique,
  verdict         text not null check (verdict in ('READY','CONDITIONAL','BLOCKED','INSUFFICIENT_EVIDENCE')),
  question_text   text,
  spec            jsonb,
  findings        jsonb not null,
  checks          jsonb not null,
  certificate     jsonb not null,
  dataset_sha256  text not null,
  policy_version  text not null
);

create index if not exists runs_dataset_idx on public.runs (dataset_sha256);
create index if not exists runs_created_idx on public.runs (created_at desc);

-- Writes happen server-side with the service key. Keep RLS on; add a read policy only
-- if the Next.js app reads directly from Supabase rather than through the API.
alter table public.runs enable row level security;

-- Append-only audit trail: block updates and deletes for every role except the owner.
create or replace function public.runs_no_mutation() returns trigger language plpgsql as $$
begin
  raise exception 'runs is append-only';
end $$;
drop trigger if exists runs_append_only on public.runs;
create trigger runs_append_only before update or delete on public.runs
  for each row execute function public.runs_no_mutation();

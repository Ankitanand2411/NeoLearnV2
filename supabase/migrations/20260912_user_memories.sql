-- Episodic memory: one row per completed tutoring session.
--
-- The backend has written to this table since V2 (services/persistence.py),
-- but no migration created it. Some existing projects have an older shape
-- (id, user_id, topic_id, summary, updated_at) that made every memory write
-- and read fail silently. This file handles both cases and is idempotent:
--   fresh project  -> creates the table with the columns the backend uses
--   existing table -> adds the missing columns in place, keeps existing ones,
--                     copies any old `summary` text into `memory_summary`

create table if not exists public.user_memories (
  id      uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  topic_id uuid not null references public.topics(id) on delete cascade
);

-- Columns the backend writes/reads. Added AFTER the create so an old-shape
-- table gains them; on a fresh table these are the first definitions.
alter table public.user_memories
  add column if not exists conversation_history jsonb not null default '[]'::jsonb,
  add column if not exists evaluation_result    jsonb not null default '{}'::jsonb,
  add column if not exists memory_summary       text,
  add column if not exists created_at           timestamptz not null default now();

-- Old-shape tables: carry the previous summary text over.
do $$
begin
  if exists (select 1 from information_schema.columns
             where table_schema = 'public' and table_name = 'user_memories' and column_name = 'summary') then
    execute 'update public.user_memories set memory_summary = summary where memory_summary is null and summary is not null';
  end if;
end $$;

create index if not exists user_memories_user_topic_idx
  on public.user_memories (user_id, topic_id, created_at desc);

alter table public.user_memories enable row level security;

-- Users may read their own memories; writes come only from the backend (service key).
drop policy if exists "user_memories_read_own" on public.user_memories;
create policy "user_memories_read_own" on public.user_memories
  for select to authenticated using (auth.uid() = user_id);

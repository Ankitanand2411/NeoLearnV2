-- Episodic memory: one row per completed tutoring session.
--
-- The backend has written to this table since V2 (services/persistence.py),
-- but no migration created it; existing projects have it from the dashboard.
-- This file makes a fresh project complete. Idempotent.

create table if not exists public.user_memories (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid not null references auth.users(id) on delete cascade,
  topic_id             uuid not null references public.topics(id) on delete cascade,
  conversation_history jsonb not null default '[]'::jsonb,
  evaluation_result    jsonb not null default '{}'::jsonb,
  memory_summary       text,
  created_at           timestamptz not null default now()
);

create index if not exists user_memories_user_topic_idx
  on public.user_memories (user_id, topic_id, created_at desc);

alter table public.user_memories enable row level security;

-- Users may read their own memories; writes come only from the backend (service key).
drop policy if exists "user_memories_read_own" on public.user_memories;
create policy "user_memories_read_own" on public.user_memories
  for select to authenticated using (auth.uid() = user_id);

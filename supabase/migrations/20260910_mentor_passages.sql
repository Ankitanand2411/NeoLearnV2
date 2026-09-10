-- Mentor primary sources for retrieval-augmented persona grounding.
--
-- Each row is one chunk of a public-domain text written by (or, for Socrates,
-- about) a mentor. Chunks carry a 768-dimensional embedding for semantic
-- search and a generated tsvector for keyword search; the hybrid function
-- fuses both rankings.
--
-- Run in the Supabase SQL editor (or `supabase db push`). Idempotent.

create extension if not exists vector;

create table if not exists public.mentor_passages (
  id          bigserial primary key,
  mentor_id   text        not null,
  source      text        not null,           -- e.g. 'Darwin, On the Origin of Species (1859), ch. 4'
  chunk_index integer     not null,
  chunk       text        not null,
  embedding   vector(768) not null,
  -- Keyword index for hybrid search. Generated column: always in sync with `chunk`.
  fts         tsvector generated always as (to_tsvector('english', chunk)) stored,
  created_at  timestamptz not null default now(),
  unique (mentor_id, source, chunk_index)
);

-- Approximate nearest-neighbour index. HNSW trades a little recall for
-- large speedups; at a few thousand rows exact scan would also be fine.
create index if not exists mentor_passages_embedding_idx
  on public.mentor_passages using hnsw (embedding vector_cosine_ops);

create index if not exists mentor_passages_fts_idx
  on public.mentor_passages using gin (fts);

create index if not exists mentor_passages_mentor_idx
  on public.mentor_passages (mentor_id);

-- Read access for the authenticated role; writes only via the service key.
alter table public.mentor_passages enable row level security;
drop policy if exists "mentor_passages_read" on public.mentor_passages;
create policy "mentor_passages_read" on public.mentor_passages
  for select to authenticated, anon using (true);


-- ─── Vector-only retrieval ────────────────────────────────────────────────────
-- `<=>` is cosine DISTANCE (0 = identical), so similarity = 1 - distance.
-- `create or replace` cannot change a function's return type, so drop first
-- (keeps the migration re-runnable when columns are added).
drop function if exists public.match_mentor_passages(text, vector, integer);
create function public.match_mentor_passages(
  p_mentor_id        text,
  p_query_embedding  vector(768),
  p_match_count      integer default 4
)
returns table (id bigint, source text, chunk_index integer, chunk text, similarity double precision)
language sql stable as $$
  select mp.id, mp.source, mp.chunk_index, mp.chunk,
         1 - (mp.embedding <=> p_query_embedding) as similarity
  from public.mentor_passages mp
  where mp.mentor_id = p_mentor_id
  order by mp.embedding <=> p_query_embedding
  limit p_match_count;
$$;


-- ─── Hybrid retrieval: vector + keyword, fused with Reciprocal Rank Fusion ────
-- RRF score = Σ 1 / (k + rank_i) over the rankings a row appears in. k = 60 is
-- the conventional constant; it damps the advantage of being rank 1 in a single
-- list so that rows ranked well by BOTH signals win. Keyword search catches
-- rare exact terms ("finch", "Galapagos") that embeddings may blur; embeddings
-- catch paraphrase that keywords miss.
drop function if exists public.match_mentor_passages_hybrid(text, text, vector, integer, integer, integer);
create function public.match_mentor_passages_hybrid(
  p_mentor_id        text,
  p_query_text       text,
  p_query_embedding  vector(768),
  p_match_count      integer default 4,
  p_candidates       integer default 20,
  p_rrf_k            integer default 60
)
returns table (id bigint, source text, chunk_index integer, chunk text, score double precision, vector_rank integer, keyword_rank integer)
language sql stable as $$
  with vec as (
    select mp.id,
           row_number() over (order by mp.embedding <=> p_query_embedding) as rnk
    from public.mentor_passages mp
    where mp.mentor_id = p_mentor_id
    order by mp.embedding <=> p_query_embedding
    limit p_candidates
  ),
  kw as (
    select mp.id,
           row_number() over (order by ts_rank_cd(mp.fts, websearch_to_tsquery('english', p_query_text)) desc) as rnk
    from public.mentor_passages mp
    where mp.mentor_id = p_mentor_id
      and mp.fts @@ websearch_to_tsquery('english', p_query_text)
    order by ts_rank_cd(mp.fts, websearch_to_tsquery('english', p_query_text)) desc
    limit p_candidates
  ),
  fused as (
    select coalesce(v.id, k.id) as id,
           coalesce(1.0 / (p_rrf_k + v.rnk), 0) + coalesce(1.0 / (p_rrf_k + k.rnk), 0) as score,
           v.rnk as vector_rank,
           k.rnk as keyword_rank
    from vec v full outer join kw k on v.id = k.id
  )
  select mp.id, mp.source, mp.chunk_index, mp.chunk, f.score, f.vector_rank::integer, f.keyword_rank::integer
  from fused f
  join public.mentor_passages mp on mp.id = f.id
  order by f.score desc, mp.id
  limit p_match_count;
$$;

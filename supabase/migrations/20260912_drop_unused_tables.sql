-- OPTIONAL and DESTRUCTIVE. Removes tables nothing in the app reads or writes:
--   quiz_sessions  (quiz state lives in the LangGraph checkpoint tables)
--   ai_eval_logs   (created by hand in an earlier version; not in the repo)
-- Back up first if you care about their contents, then run.

drop table if exists public.quiz_sessions;
drop table if exists public.ai_eval_logs;

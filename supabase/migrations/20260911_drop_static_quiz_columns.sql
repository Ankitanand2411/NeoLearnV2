-- OPTIONAL and DESTRUCTIVE. Removes the static one-question quiz columns from
-- `topics`. Questions are generated per session now; nothing in the backend or
-- frontend reads these columns. Back up the table first if the content matters
-- to you, confirm no external consumer depends on them, then run.

alter table public.topics
  drop column if exists quiz_question,
  drop column if exists quiz_options,
  drop column if exists quiz_correct_answer,
  drop column if exists video_description;

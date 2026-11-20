-- Supabase SQL Editor에 붙여 넣어 한 번 실행하세요 (글모아와 같은 프로젝트).
-- 각 PC가 "무엇을 만들었는지" 기록만 계정에 모읍니다. 파일(영상·이미지)은 올라가지 않습니다.
-- 본인 행만 읽고 쓸 수 있습니다(RLS).

create table if not exists public.shorts_project_log (
  user_id    uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  device     text        not null,
  project_id text        not null,
  title      text        not null default '',
  step       text        not null default '',
  rendered   boolean     not null default false,
  uploaded   boolean     not null default false,
  archived   boolean     not null default false,
  updated_at timestamptz not null default now(),
  primary key (user_id, device, project_id)
);

create table if not exists public.shorts_topic_log (
  user_id    uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  topic_id   text        not null,
  title      text        not null default '',
  project_id text,
  updated_at timestamptz not null default now(),
  primary key (user_id, topic_id)
);

alter table public.shorts_project_log enable row level security;
alter table public.shorts_topic_log   enable row level security;

drop policy if exists "own rows" on public.shorts_project_log;
create policy "own rows" on public.shorts_project_log
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "own rows" on public.shorts_topic_log;
create policy "own rows" on public.shorts_topic_log
  for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

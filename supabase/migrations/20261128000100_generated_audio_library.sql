alter table public.voice_samples
  add column if not exists reference_text text;

create table if not exists public.generated_audio (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  voice_model_id uuid null,
  title text not null default 'تسجيل صوتي جديد',
  text_content text not null,
  provider text not null default 'omnivoice',
  storage_path text not null unique,
  mime_type text not null default 'audio/wav',
  size_bytes bigint not null check (size_bytes > 0),
  duration_ms integer null check (duration_ms is null or duration_ms > 0),
  created_at timestamptz not null default now(),
  constraint generated_audio_voice_model_owner_fkey
    foreign key (voice_model_id, user_id)
    references public.voice_models(id, user_id)
    on delete set null
);

create index if not exists generated_audio_user_created_idx
  on public.generated_audio(user_id, created_at desc);

alter table public.generated_audio enable row level security;
grant select, insert, delete on public.generated_audio to authenticated;

create policy generated_audio_select_own
  on public.generated_audio for select to authenticated
  using ((select auth.uid()) = user_id);

create policy generated_audio_insert_own
  on public.generated_audio for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy generated_audio_delete_own
  on public.generated_audio for delete to authenticated
  using ((select auth.uid()) = user_id);

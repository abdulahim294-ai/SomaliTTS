alter table public.generated_audio
  drop constraint if exists generated_audio_voice_model_owner_fkey;

alter table public.generated_audio
  add constraint generated_audio_voice_model_owner_fkey
  foreign key (voice_model_id, user_id)
  references public.voice_models(id, user_id)
  on delete cascade;

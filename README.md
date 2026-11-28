# SomaliTTS

SomaliTTS is a mobile-first Arabic interface for generating Somali voiceovers with a saved personal voice sample.

## Current web studio

- Static frontend in `web/index.html`, published from the `web/` directory on Netlify.
- Voice cloning runs directly against the public `k2-fsa/OmniVoice` Hugging Face Space using its Gradio API. The browser uploads the reference sample to the Space for inference; Hugging Face queue and ZeroGPU availability determine generation time.
- Supabase Auth provides a per-browser anonymous account. Supabase Storage keeps reference recordings and generated WAV files in private buckets.
- Supabase Database stores voice sample metadata and generated audio history. Row Level Security restricts records and files to the owning account.
- The same saved Somali voice is reused for each new script; generated files can be played, downloaded, and deleted from the private library.

## Supabase setup

The project uses Supabase project `eczhhuhwrxfuzfczycug`.

Required private buckets:
- `voice-samples`
- `generated-audio`

Database tables include `voice_models`, `voice_samples`, and `generated_audio`. SQL migrations are in `supabase/migrations/`.

The frontend uses the Supabase publishable key only. Do not place a service-role key or Hugging Face access token in browser code. Anonymous sign-ins must be enabled in Supabase Auth for first-time browser sessions.

## Hugging Face

- Space: https://huggingface.co/spaces/k2-fsa/OmniVoice
- Repository: https://github.com/k2-fsa/OmniVoice
- Somali is included in the model's language map.
- The Space may sleep, queue requests, or enforce free ZeroGPU limits. A successful UI connection does not guarantee immediate inference availability.
- The repository README and model card contain the current model/weights licensing terms. The integration is intended for personal, non-commercial use unless the applicable model license explicitly permits otherwise.

## Deploy to Netlify

Connect this GitHub repository to the existing Netlify site and use the repository root as the base directory. The included `netlify.toml` publishes `web/` without a build command.

## Legacy API

`app.py` and the FastAPI endpoints remain in the repository for local development and legacy deployments. The current static Netlify studio does not depend on the Render service.

## Privacy

Only upload your own voice or a recording you have permission to use. Reference recordings and generated files are stored in private Supabase buckets, but the reference sample is also transmitted to Hugging Face for voice generation.

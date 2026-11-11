# Hubi-TTS inference adapter

A private FastAPI inference service for the Somali Voice Studio Hubi adapter. It is separate from the existing Render Edge-TTS service and does not change it.

## Model and risk

- Model: `ayeeyokoris/hubi-tts`
- Model usage example documented by the publisher: `AutoModel.from_pretrained(..., trust_remote_code=True)`, then `model.tts(text, prompt_audio="reference.wav", save_path="output.wav")`.
- The model repository is very new. Review all custom model code and establish a pinned commit and license status before production or commercial use. The default revision `main` is for initial experimentation only.
- Run on a CUDA GPU. CPU may technically load but can be slow and memory intensive.

## Environment

Set these server-side only:

- `HUBI_API_TOKEN`: long random bearer secret, required.
- `HUBI_MODEL_ID`: optional, defaults to `ayeeyokoris/hubi-tts`.
- `HUBI_MODEL_REVISION`: optional, defaults to `main`; replace with reviewed immutable commit before production.
- `HUBI_MAX_UPLOAD_BYTES`: optional, defaults to 25 MiB.

Never put `HUBI_API_TOKEN` in a browser, Vite variable, public notebook output, or Git repository.

## API contract

All routes except the health probe require `Authorization: Bearer <HUBI_API_TOKEN>`.

- `GET /health` returns `{ "ready": true, "model": "...", "device": "cuda" }` only after model loading.
- `POST /prepare` multipart fields: `voice_id`, `language=so`, `reference_audio`. It normalizes the reference with FFmpeg and runs a short real synthesis probe. Only successful output returns `{ "voice_id": "<same id>", "ready": true }`.
- `POST /tts` multipart fields: `text`, `voice_id`, `language=so`, `reference_audio`. Returns actual WAV bytes with `Content-Type: audio/wav`.

The caller (Somali Voice Studio server adapter) must authenticate the user, verify ownership of the selected voice and private sample, and download that sample from private Storage. This inference service trusts only its bearer token; it does not authenticate end users or access Supabase.

## Run on a CUDA host

```bash
pip install -r requirements.txt
export HUBI_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
uvicorn app:app --host 0.0.0.0 --port 7860
```

For a temporary Kaggle session, start the service in the notebook and expose it using an authenticated HTTPS tunnel. The tunnel URL and same token must be configured as `HUBI_TTS_URL` and `HUBI_TTS_TOKEN` in the Somali Voice Studio server environment. The tunnel dies when the Kaggle session stops.

## Important limitations

This is a first inference adapter, not a durable public hosting solution. It serializes model calls, stores no user audio persistently, and has no queue, autoscaling, rate-limit policy, or durable job store. Keep the tunnel private and do not share the URL/token. The service must be run on a trusted GPU environment. Do not expose a raw Gradio public share URL as an unauthenticated public API.

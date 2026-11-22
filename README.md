# SomaliTTS

SomaliTTS is a first-party Somali voice studio and FastAPI service. The web interface is served directly by this repository; it does not require Lovable at runtime.

## Web studio

- `/` — standalone responsive studio UI (Arabic RTL, mobile-first).
- `/clone` — opens the same studio on the voice-cloning tab.
- Text-to-speech: Somali male Muuse and female Ubax voices through Microsoft Edge TTS.
- Voice cloning: hosted `k2-fsa/OmniVoice` Space through the server-side Gradio client. The browser never receives a provider token.
- Generated TTS is returned as MP3 after FFmpeg normalization; cloned audio is returned as WAV.

## API

- `GET /api/v1/health` — application liveness.
- `GET /api/v1/health/ready` — bounded Edge TTS provider readiness check.
- `GET /api/v1/capabilities` — configured provider and audio capabilities.
- `POST /tts` — multipart form fields: `text`, `gender` (`male` or `female`); returns `audio/mpeg`.
- `POST /api/v1/clone` — multipart form fields: `text`, `reference_text`, `instruction` (optional), `reference_audio`; returns `audio/wav`.

## Architecture

The UI is plain HTML/CSS/JavaScript served by FastAPI, so there is no Lovable runtime dependency or separate frontend hosting requirement. Edge TTS remains the normal Somali TTS engine. OmniVoice is a separate hosted voice-cloning engine; the model does not run on the small Render instance.

OmniVoice availability and free ZeroGPU quota are controlled by Hugging Face. Its published model weights are licensed CC-BY-NC, so this integration is for non-commercial testing and personal use only unless the model owner grants separate commercial rights. Do not upload another person's voice without their explicit permission.

The service does not promise permanent storage of reference recordings or generated audio. The current clone endpoint processes the reference in a temporary server directory and forwards it to the hosted OmniVoice Space.

## Run locally

Python 3.11 is recommended:

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 10000
```

Install FFmpeg separately for local TTS audio processing. The Dockerfile installs FFmpeg automatically.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests cover the API and UI routes and mock Edge TTS. They do not replace a live end-to-end test against the hosted OmniVoice Space.

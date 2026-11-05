# SomaliTTS

SomaliTTS is a FastAPI service that returns Somali speech as MP3 using configured Microsoft Edge TTS voices.

## Current capabilities

- Muuse (`so-SO-MuuseNeural`, male) and Ubax (`so-SO-UbaxNeural`, female).
- `GET /api/v1/health` is application liveness. `GET /api/v1/health/ready` performs a short, cached upstream voice-list check and can return degraded/503.
- `GET /api/v1/capabilities` reports configured functionality; it does not assert live upstream availability.
- Existing `POST /tts` multipart form API remains supported and returns `audio/mpeg`.
- Voice cloning, public voice sharing, durable long-form jobs, and genuine emotional synthesis are unavailable.

## Voice cloning research

The proposed research path is Somali TTS (Jelle/Diirow) followed by RVC voice conversion. It is not yet implemented or validated; the current service still uses Edge TTS. See [the feasibility and architecture decision](docs/VOICE_PIPELINE_FEASIBILITY.md) for model licensing, compute limits, privacy gates, and prototype acceptance criteria.

### GPU baseline experiment

A Kaggle notebook is provided at [`notebooks/somali_speecht5_baseline.ipynb`](notebooks/somali_speecht5_baseline.ipynb). It compares the Jelle and Diirow SpeechT5 checkpoints and saves sample WAVs plus a manifest of exact model revisions. It requires a Kaggle GPU and internet access, and it has **not yet been executed or quality-validated**. It uses a public CMU ARCTIC speaker embedding only for a preliminary technical check; it does not clone a user's voice. Do not proceed to RVC until a Somali-speaking listener confirms that at least one baseline is intelligible.

## Run locally

Python 3.11 is recommended:

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 10000
```

See [docs/API.md](docs/API.md), [docs/SECURITY.md](docs/SECURITY.md), and [docs/RENDER_DEPLOYMENT.md](docs/RENDER_DEPLOYMENT.md). No new paid service or runtime dependency is introduced. Edge TTS requires outbound connectivity; readiness is a bounded network check, not a guarantee of successful speech generation.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests mock Edge TTS and do not consume provider credits or validate live audio.

# SomaliTTS

SomaliTTS is a small FastAPI service that returns Somali speech as an MP3 using the Microsoft Edge TTS voices currently configured by this project.

## Current capabilities

- Speech synthesis through Edge TTS using `so-SO-MuuseNeural` (Muuse, male) and `so-SO-UbaxNeural` (Ubax, female).
- `GET /api/v1/health` for service liveness and `GET /api/v1/capabilities` for the configured provider and feature flags.
- Existing `POST /tts` form interface remains supported.
- Voice cloning, public voice sharing, durable long-form jobs, and genuine emotional synthesis are not implemented and are reported as unavailable.

The capability response describes configured integration, not the live reachability of Microsoft's external service. Edge TTS requires outbound network access and can fail independently of this API.

## Run locally

Python 3.11 is recommended. Install dependencies and start the API:

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 10000
```

No new runtime dependencies are required. The existing pinned `edge-tts` dependency is used for speech synthesis.

## API

See [docs/API.md](docs/API.md) for request/response details and integration guidance for Lovable. Interactive FastAPI documentation is available at `/docs` when the service is running.

### Existing synthesis endpoint

`POST /tts` accepts form fields `text` (required, non-empty, up to 100,000 characters) and `gender` (optional: `male` or `female`, default `male`). It returns an `audio/mpeg` attachment named `somali_voice.mp3`.

```bash
curl -f -X POST https://somalitts.onrender.com/tts \
  -F 'text=Salaan, sidee tahay?' \
  -F 'gender=female' \
  --output somali_voice.mp3
```

Long text is split into sequential requests of at most 2,500 characters and MP3 data is joined in memory. This is a synchronous request, not a durable background job. The existing 100,000-character input limit is not a promise of successful synthesis at that length.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests use a fake Edge TTS stream and do not contact Microsoft or prove live audio quality/service availability.

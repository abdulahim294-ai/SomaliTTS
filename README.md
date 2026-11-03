# SomaliTTS

A small FastAPI service that returns Somali speech as an MP3 using Microsoft Edge TTS voices.

## Voices

- `male` (default): `so-SO-MuuseNeural`
- `female`: `so-SO-UbaxNeural`

## Run locally

Python 3.11 is recommended. Install dependencies and start the API:

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 10000
```

The API requires outbound network access to Microsoft's Edge TTS speech service. The `edge-tts` dependency is pinned to 7.3.1, which includes upstream support for the Sec-MS-GEC v2 token format introduced in Microsoft's October 2026 protocol change. Older edge-tts releases used the v1 token format and can receive WebSocket HTTP 403 responses. Upstream issue reports describe the protocol/token mismatch; the repository alone cannot show which version was installed in a previously built Render image because the former requirements were unpinned.

This change addresses the known library-side protocol mismatch. A successful response from Render still depends on Microsoft's service being reachable and accepting requests; no live Render access or real provider synthesis was available to verify that here. The 403 alone does not establish a Render network restriction.

## API

`POST /tts` accepts the existing form fields and returns an `audio/mpeg` attachment:

- `text` (required; non-empty; maximum 100,000 characters)
- `gender` (optional; `male` or `female`, defaults to `male`)

Example:

```bash
curl -f -X POST https://somalitts.onrender.com/tts \\
  -F 'text=Salaan, sidee tahay?' \\
  -F 'gender=female' \\
  --output somali_voice.mp3
```

Long text is split into sequential requests of at most 2,500 characters, then MP3 segments are joined in memory. Requests use isolated in-memory buffers, so they do not share or leave temporary audio files. Invalid input returns HTTP 422/413; provider errors return 502 and provider timeouts return 504.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Tests mock speech generation and verify voice selection, MP3 response headers/content, provider failures, and long-text chunking. They do not prove that Microsoft generated playable audio; that requires an end-to-end request against the live provider.

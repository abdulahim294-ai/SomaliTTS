# API guide for Lovable integrations

Base URL currently documented: `https://somalitts.onrender.com`; use your actual deployment base URL in other environments. No application API key is currently required or supported.

## Liveness and readiness

`GET /api/v1/health` is a lightweight application liveness endpoint and makes no upstream request:

```json
{"status":"ok","service":"SomaliTTS","api_version":"v1"}
```

`GET /api/v1/health/ready` checks whether the configured Edge TTS provider responds to a bounded upstream voice-list request. Results are cached briefly. A 200 response means the provider check succeeded; 503 means the app is alive but provider readiness is degraded. This is not a full synthesis test and does not guarantee future requests succeed.

## Capabilities and voices

`GET /api/v1/capabilities` lists configured providers and features. Muuse is `so-SO-MuuseNeural` (male, `so-SO`); Ubax is `so-SO-UbaxNeural` (female, `so-SO`). `configured` does not mean reachable. Cloning, public sharing, durable jobs, and genuine emotional synthesis are unavailable.

## Existing synthesis API

`POST /tts` accepts `multipart/form-data`:

| Field | Required | Values / limits |
| --- | --- | --- |
| `text` | yes | Non-whitespace; at most 100,000 characters |
| `gender` | no | `male` (default) or `female` |

Success returns raw MP3 bytes, `Content-Type: audio/mpeg`, attachment `somali_voice.mp3`.

```javascript
const form = new FormData();
form.append("text", "Salaan, sidee tahay?");
form.append("gender", "female");
const response = await fetch("https://somalitts.onrender.com/tts", { method: "POST", body: form });
if (!response.ok) {
  const problem = await response.json();
  throw new Error(`${problem.error?.code || response.status}: ${problem.error?.message || "TTS failed"}`);
}
const audioUrl = URL.createObjectURL(await response.blob());
```

Do not set multipart `Content-Type` manually in browser `FormData`. Typical errors: 422 invalid input, 413 text too large, 429 in-process rate limit, 503 temporary capacity exhaustion, 502 provider failure, 504 timeout. JSON errors have a stable `error.code`, safe `error.message`, and `error.request_id`; `detail` is retained for compatibility. `X-Request-ID` is returned on responses; clients may supply a safe 1–128 character `[A-Za-z0-9._-]` ID.

## Browser and reliability

Browser access is controlled by `CORS_ALLOWED_ORIGINS`. Add the exact deployed Lovable origin to that environment variable after confirming the final domain; no Lovable domain is guessed or hardcoded. See [SECURITY.md](SECURITY.md). In-memory rate/concurrency limits apply per process, not globally across multiple instances. Synthesis is synchronous and buffers audio in memory; text chunking is not a durable job system.

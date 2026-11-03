# Initial architecture

## Scope

The service is a synchronous FastAPI application. Its supported synthesis path accepts a form-encoded text/gender request at the legacy `POST /tts` route and returns an MP3 attachment. Versioned read-only endpoints expose liveness and configured capabilities.

## Request path

1. `app.py` validates input, maps `male`/`female` to the configured Edge voice IDs, and preserves the existing HTTP response/error contract.
2. The route delegates synthesis to the registered provider instance rather than constructing the provider client itself.
3. `providers/base.py` defines the voice/provider contract and registry; `providers/edge.py` implements the Edge TTS adapter and bounded text chunking.
4. Provider audio is collected in memory and returned as `audio/mpeg`. No files or background jobs are created.

## Capability reporting

`GET /api/v1/capabilities` serializes metadata from registered providers. Voice metadata is explicit and includes the upstream ID, display name, gender, and locale. `configured` means configured in application code; it is not a runtime connectivity probe. Feature flags are conservative: only text-to-speech is true. Voice cloning, public voice sharing, durable long-form jobs, and emotional synthesis remain false until built and verified.

`GET /api/v1/health` is a liveness endpoint and does not make an outbound request. It must not be interpreted as upstream provider health.

## Boundaries and next steps

- Current synthesis depends on outbound access to Microsoft's Edge TTS service.
- Current request processing and audio buffering are synchronous/in-memory; no persistence or job lifecycle exists.
- No authentication, API key, browser CORS policy, voice cloning, or public sharing is implemented.
- Add future provider implementations behind `SpeechProvider`; report only their verified capabilities. Add integration tests for provider error/timeout mapping and contract tests for every provider.
- Before exposing browser integrations, define and test allowed origins. Before durable jobs or long-form generation, design persistence, job status/state transitions, quotas, cancellation, and cleanup rather than representing request chunking as a job system.

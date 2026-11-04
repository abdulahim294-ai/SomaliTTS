# Architecture

## Request and provider path

FastAPI validates legacy `POST /tts`, maps gender to Muuse/Ubax, applies per-process rate and concurrency guards, and delegates to `EdgeTTSProvider`. Provider audio is collected in memory and returned as an MP3 attachment. Input chunks are processed sequentially. Bounded transient retries only apply to the currently failing chunk before any audio bytes for that chunk are received; prior completed chunks are not replayed. A total request deadline bounds the operation.

`providers/base.py` defines synthesis and health-check contracts, voice metadata, and the registry. The Edge health check queries the upstream voice list (not speech generation), verifies both configured Somali voices, and is bounded/cached by the API. Package installation alone is never taken as reachability. `/api/v1/health` is liveness; `/api/v1/health/ready` distinguishes app alive, provider configured, and provider reachable.

## Middleware and controls

CORS uses explicit origins, no credentials, and no wildcard. Request middleware accepts only a restricted request-ID character set, otherwise generates a random ID; it returns that ID and logs JSON metadata (method, path, status, duration, ID). It does not log request content, authorization headers, or audio. Public errors have stable safe codes/messages and request IDs.

Rate counting and an asyncio semaphore are in-memory and per process. Client identity is the direct socket peer; `X-Forwarded-For` and similar headers are not trusted. Multi-process deployments therefore need an external gateway for global quotas, if global enforcement is required. Semaphore acquisition has a bounded wait and is released in `finally`, including cancellation/error paths.

## Environment

See `docs/SECURITY.md` and `docs/RENDER_DEPLOYMENT.md` for defaults and configuration. No secrets are currently needed by this application. The Edge upstream is external and can change or be unavailable. Health checks are not a guarantee that a subsequent synthesis succeeds.

## Explicit non-goals

No authentication, voice cloning, public voice sharing, durable jobs, persistence, or genuine emotional synthesis is implemented. No Render production settings are changed by this code.

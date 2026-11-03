# Security and operational configuration

Configuration is through environment variables; defaults are suitable for local development and conservative single-process use. Numeric values are clamped to valid minimums; malformed numeric values fall back to their documented defaults.

| Variable | Default | Purpose |
| --- | --- | --- |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated exact browser origins. No wildcard is accepted. Add the final Lovable production origin only after it is known, e.g. set the value to existing origins plus `https://your-confirmed-domain`. |
| `PROVIDER_HEALTH_TIMEOUT_SECONDS` | `3` | Maximum duration for upstream voice-list health probe. |
| `PROVIDER_HEALTH_CACHE_SECONDS` | `15` | Duration to cache reachable/unreachable readiness result. |
| `TTS_RATE_LIMIT_REQUESTS` | `10` | Requests per client process-local rate window. |
| `TTS_RATE_LIMIT_WINDOW_SECONDS` | `60` | Fixed rate-limit window in seconds. |
| `TTS_MAX_CONCURRENT` | `2` | Simultaneous provider synthesis operations per process. |
| `TTS_CONCURRENCY_WAIT_SECONDS` | `2` | Maximum time waiting for a synthesis slot. |
| `TTS_REQUEST_TIMEOUT_SECONDS` | `300` | Total deadline for one synthesis request. |
| `PROVIDER_RETRY_ATTEMPTS` | `2` | Total attempts per current chunk, clamped to 1–3. |
| `PROVIDER_RETRY_BASE_SECONDS` | `0.2` | Exponential retry delay base, with jitter. |

CORS has credentials disabled; `*` is rejected. Browsers must match an exact configured origin. If Lovable needs a production URL, configure its confirmed origin on the deployment environment; do not use a guessed domain. CORS is not authentication.

Request IDs are accepted only when they match `[A-Za-z0-9._-]{1,128}`; invalid values are replaced. Logs contain JSON request metadata and provider failure categories, not submitted text, audio, authorization headers, or exception messages. Do not add tokens or secrets to log fields. The service currently does not consume API keys.

Rate limiting and concurrency controls are in-memory per process and are not distributed quotas. The client address is taken from the direct connection peer; forwarding headers are ignored to prevent spoofing. If deployed behind a proxy, configure trusted-proxy handling at a known ingress layer before relying on per-client identity. Avoid exposing the app directly if an ingress is required.

Retry is limited to connection/OS failures before audio bytes arrive for the current text chunk. A partially streamed chunk is not retried. This minimizes duplicate upstream work but cannot guarantee provider-side idempotency. Input validation errors are never retried. Health checks make a remote voice-list call, not a speech generation call.

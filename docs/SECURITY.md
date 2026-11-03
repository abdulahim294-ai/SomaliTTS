# Security and operational configuration

Configuration is parsed once at process startup by `config.py`. Invalid numeric values use defaults; finite values are clamped to stated bounds.

| Variable | Default | Effective bounds / purpose |
| --- | --- | --- |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Exact comma-separated origins; wildcard rejected; credentials disabled. |
| `PROVIDER_HEALTH_TIMEOUT_SECONDS` | `3` | 0.1–15 seconds. |
| `PROVIDER_HEALTH_CACHE_SECONDS` | `15` | 1–300 seconds. |
| `TTS_RATE_LIMIT_REQUESTS` | `10` | 1–10,000 per process window. |
| `TTS_RATE_LIMIT_WINDOW_SECONDS` | `60` | 1–3,600 seconds. |
| `TTS_RATE_LIMIT_MAX_CLIENTS` | `4096` | 32–100,000 tracked client keys; stale entries are swept and the oldest key evicted under capacity pressure. |
| `TTS_MAX_CONCURRENT` | `2` | 1–100 concurrent synthesis operations per process. |
| `TTS_CONCURRENCY_WAIT_SECONDS` | `2` | 0.05–60 seconds. |
| `TTS_REQUEST_TIMEOUT_SECONDS` | `300` | 1–900 seconds; shared by API and provider through immutable startup settings. |
| `PROVIDER_RETRY_ATTEMPTS` | `2` | 1–3 total attempts for eligible current-chunk failures. |
| `PROVIDER_RETRY_BASE_SECONDS` | `0.2` | 0.05–5 seconds, exponential backoff with jitter. |
| `MAX_REQUEST_BODY_BYTES` | `1048576` | 524,288–10,485,760 raw request-body bytes. Enforced before multipart parsing. The minimum allows 100,000 four-byte UTF-8 characters plus multipart framing. |

Limits are process-local, not global. The rate limiter bounds tracked-client memory and expires stale keys; eviction can allow a client that was evicted to begin a new window. Client identity uses the direct peer address only; forwarding headers are ignored. Configure known ingress limits separately if distributed/global quotas are required.

CORS is not authentication. Add only the exact, confirmed Lovable production origin to `CORS_ALLOWED_ORIGINS`. Never guess the production domain. No credentials or wildcard origins are enabled. Logs include request metadata and safe provider categories, not request text, audio, authorization values, exception messages, or secrets. Request IDs accept only `[A-Za-z0-9._-]{1,128}`.

The raw body cap protects multipart parsing from oversized payloads; the endpoint separately enforces a 100,000-character text limit. Keep the cap above the maximum UTF-8 encoded text size plus multipart framing. Speech generation remains synchronous and in memory. Transient retries apply only before audio bytes arrive for the current chunk; prior completed chunks are not replayed.

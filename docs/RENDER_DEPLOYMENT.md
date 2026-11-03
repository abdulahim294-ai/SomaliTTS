# Render deployment notes

This hardening change does not change Render production settings, service commands, or deploy the service. Existing Dockerfile dependency and Uvicorn launch configuration remain compatible.

## Optional environment settings

| Variable | Default | Notes |
| --- | --- | --- |
| `CORS_ALLOWED_ORIGINS` | localhost:3000 and 127.0.0.1:3000 | Set confirmed exact origins, comma-separated. Add Lovable production origin only after it is known. |
| `PROVIDER_HEALTH_TIMEOUT_SECONDS` | 3 | Bounded readiness upstream check. |
| `PROVIDER_HEALTH_CACHE_SECONDS` | 15 | Per-process readiness cache. |
| `TTS_RATE_LIMIT_REQUESTS` | 10 | Requests per fixed process-local window. |
| `TTS_RATE_LIMIT_WINDOW_SECONDS` | 60 | 60 seconds. |
| `TTS_RATE_LIMIT_MAX_CLIENTS` | 4096 | Maximum tracked client keys. |
| `TTS_MAX_CONCURRENT` | 2 | Per-process synthesis slots. |
| `TTS_CONCURRENCY_WAIT_SECONDS` | 2 | Maximum wait for a slot. |
| `TTS_REQUEST_TIMEOUT_SECONDS` | 300 | Shared API/provider deadline. |
| `PROVIDER_RETRY_ATTEMPTS` | 2 | Maximum configured total current-chunk attempts (hard cap 3). |
| `PROVIDER_RETRY_BASE_SECONDS` | 0.2 | Jittered exponential backoff base. |
| `MAX_REQUEST_BODY_BYTES` | 1048576 | Bounded raw request size before form parsing. |

Numeric values are parsed at process start; invalid values use defaults and out-of-range values are clamped. Full bounds are listed in `SECURITY.md`. No keys are required.

## Health and scaling

Use `/api/v1/health` for liveness and `/api/v1/health/ready` for a cached upstream provider check. Readiness can return 503 when provider reachability is degraded; it does not guarantee synthesis availability. Rate/concurrency state is in-memory and per process, not global across Render instances or workers. The app ignores `X-Forwarded-For`; do not rely on these limits as a distributed quota. Use a trusted ingress policy for global controls if needed.

The body-size middleware rejects oversized requests before multipart parsing. Preserve enough proxy/request limits to allow normal form submissions. The existing text limit remains 100,000 characters. Validate Docker and tests before separately choosing to deploy; no deployment has been run as part of this change.

# Render deployment notes

This change intentionally does not alter Render service settings, start commands, build commands, or production environment values. The existing Dockerfile still installs `requirements.txt` and starts `uvicorn app:app --host 0.0.0.0 --port 10000`; no additional runtime package is required.

## Configure environment values

Set optional environment variables through the Render service dashboard only after reviewing the values:

- `CORS_ALLOWED_ORIGINS`: comma-separated exact origins. The application defaults to localhost development origins. Add the confirmed Lovable site origin before enabling browser calls; no production Lovable hostname is assumed.
- `PROVIDER_HEALTH_TIMEOUT_SECONDS` (3) and `PROVIDER_HEALTH_CACHE_SECONDS` (15): readiness probe timing.
- `TTS_RATE_LIMIT_REQUESTS` (10) and `TTS_RATE_LIMIT_WINDOW_SECONDS` (60): per-process fixed-window limit.
- `TTS_MAX_CONCURRENT` (2), `TTS_CONCURRENCY_WAIT_SECONDS` (2), and `TTS_REQUEST_TIMEOUT_SECONDS` (300): process capacity and request deadline.
- `PROVIDER_RETRY_ATTEMPTS` (2, max 3) and `PROVIDER_RETRY_BASE_SECONDS` (0.2): bounded transient current-chunk retry.

No keys/secrets are required by the current app. Do not add secrets to the repository or deployment logs.

## Health checks and scaling

Use `/api/v1/health` for liveness. `/api/v1/health/ready` makes a bounded upstream voice-list request and returns 503 when provider reachability is degraded; results are cached briefly. Do not interpret liveness as provider health. This change does not request or modify Render health-check configuration.

Rate and concurrency limits are per application process and do not coordinate across Render instances/workers. A shared ingress/rate-limiting service is needed for global quotas. The app does not trust forwarded client IP headers. Validate the actual proxy topology before adding trusted proxy support.

## Validation

Build/test in CI or a local Docker-capable environment before deploying. Dockerfile configuration is unchanged; production deployment has not been run or verified by this code change.

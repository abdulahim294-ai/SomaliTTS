# API guide for Lovable integrations

Base URL for the currently documented deployment: `https://somalitts.onrender.com`. Replace it with the API's actual deployment URL for other environments. No API key is currently required or supported.

## Discover service health

`GET /api/v1/health`

Returns liveness only; it does not call Microsoft Edge TTS or guarantee that speech generation is currently reachable.

```json
{
  "status": "ok",
  "service": "SomaliTTS",
  "api_version": "v1"
}
```

## Discover capabilities and voices

`GET /api/v1/capabilities`

The configured voices are:

- `so-SO-MuuseNeural` — Muuse, male, Somali (`so-SO`)
- `so-SO-UbaxNeural` — Ubax, female, Somali (`so-SO`)

The response includes the provider's feature flags. `configured: true` means the provider is set up in this application; it is not a live upstream health check. Voice cloning, public voice sharing, durable long-form jobs, and genuine emotional synthesis are reported as unavailable.

## Generate audio (existing compatibility endpoint)

`POST /tts` consumes `multipart/form-data` (HTML form fields):

| Field | Required | Values / limits |
| --- | --- | --- |
| `text` | Yes | Non-whitespace text; maximum 100,000 characters |
| `gender` | No | `male` (default) or `female` |

A successful request returns raw MP3 bytes with `Content-Type: audio/mpeg` and an attachment filename of `somali_voice.mp3`. It does not return JSON or a URL. Store or play the response as a binary audio blob in the client. Example:

```javascript
const form = new FormData();
form.append("text", "Salaan, sidee tahay?");
form.append("gender", "female");
const response = await fetch("https://somalitts.onrender.com/tts", {
  method: "POST",
  body: form,
});
if (!response.ok) throw new Error(`TTS failed: ${response.status}`);
const audioBlob = await response.blob();
const audioUrl = URL.createObjectURL(audioBlob);
// Set an audio element's src to audioUrl; revoke it when no longer needed.
```

Do not set the multipart `Content-Type` header manually when using browser `FormData`; the browser must add its boundary. Errors use FastAPI JSON `detail` responses. Common statuses are `422` for invalid input, `413` for text exceeding the limit, `502` for provider failure, and `504` for timeout.

## Browser and reliability notes

This API does not currently configure browser CORS policy. A Lovable app calling the API directly from a browser may be blocked by the browser unless the deployed service explicitly permits that app's origin. Use a server-side integration/proxy you control or configure a reviewed, allow-listed CORS policy in a later milestone; do not assume CORS is enabled.

Synthesis is synchronous, uses the external Edge TTS service, and holds audio in memory. Long inputs are split into sequential chunks, but there is no durable job queue, persistence, or guaranteed completion for long-form requests. Do not retry non-idempotently without considering duplicate provider work.

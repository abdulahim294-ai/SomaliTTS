from starlette.responses import JSONResponse


class RequestBodyLimitMiddleware:
    """Buffer requests only up to the configured cap before form parsing."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                headers = dict(scope.get("headers", []))
                incoming_id = headers.get(b"x-request-id", b"").decode("ascii", "ignore")
                import re, secrets
                request_id = incoming_id if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", incoming_id) else secrets.token_hex(16)
                body = {
                    "detail": "Request body exceeds the configured limit",
                    "error": {"code": "request_too_large", "message": "Request body exceeds the configured limit",
                              "request_id": request_id},
                }
                response = JSONResponse(status_code=413, content=body,
                                        headers={"X-Request-ID": request_id})
                await response(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        sent = False
        async def replay_receive():
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": b"".join(chunks), "more_body": False}

        await self.app(scope, replay_receive, send)

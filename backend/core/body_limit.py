"""Bound JSON request memory before parsing or authentication."""

from starlette.responses import JSONResponse


class RequestBodyLimit:
    def __init__(self, app, maximum=2 * 1024 * 1024):
        self.app = app
        self.maximum = maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = self.maximum + 1
        if length < 0 or length > self.maximum:
            return await JSONResponse({"detail": "Anfrage zu groß."}, status_code=413)(
                scope, receive, send
            )
        size, chunks = 0, []
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] == "http.request":
                size += len(message.get("body", b""))
                if size > self.maximum:
                    return await JSONResponse(
                        {"detail": "Anfrage zu groß."}, status_code=413
                    )(scope, receive, send)
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
        body, delivered = b"".join(chunks), False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self.app(scope, bounded_receive, send)

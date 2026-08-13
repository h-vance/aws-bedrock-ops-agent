import os
import time
from collections import defaultdict, deque

from starlette.responses import JSONResponse

RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "3600"))
RATE_LIMITED_PATHS = ("/triage", "/mcp")

_request_log: dict[str, deque] = defaultdict(deque)


def reset():
    """Clear all tracked request history. Intended for test isolation."""
    _request_log.clear()


class RateLimitMiddleware:
    """Per-client-IP sliding-window limiter for the endpoints that can trigger
    a live Bedrock call (/triage, /mcp). Bounds cost/abuse exposure if a
    deployment ever flips BEDROCK_MOCK off; harmless in mock mode.

    Plain ASGI middleware (not BaseHTTPMiddleware) so it never buffers or
    interferes with the MCP endpoint's streamed responses on the allowed path.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not any(
            scope["path"].startswith(p) for p in RATE_LIMITED_PATHS
        ):
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        now = time.monotonic()
        window = _request_log[client_ip]
        while window and now - window[0] > RATE_LIMIT_WINDOW_SECONDS:
            window.popleft()

        if len(window) >= RATE_LIMIT_REQUESTS:
            response = JSONResponse(
                {"detail": "Rate limit exceeded. Try again later."},
                status_code=429,
            )
            await response(scope, receive, send)
            return

        window.append(now)
        await self.app(scope, receive, send)

"""HTTP hardening: security headers and a small in-process rate limiter."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# (path prefix, max requests, window seconds) — checked per client IP.
LIMITS: Tuple[Tuple[str, int, int], ...] = (
    ("/api/auth/otp/request", 10, 600),
    ("/api/auth/otp/verify", 30, 600),
    ("/api/events", 120, 60),
    ("/api/errors", 30, 60),
    ("/api/", 600, 60),
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limits=LIMITS):
        super().__init__(app)
        self.limits = limits
        self.hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    async def dispatch(self, request, call_next):
        path = request.url.path
        ip = request.client.host if request.client else "?"
        now = time.time()
        for prefix, cap, window in self.limits:
            if not path.startswith(prefix):
                continue
            with self.lock:
                q = self.hits[(ip, prefix)]
                while q and q[0] < now - window:
                    q.popleft()
                if len(q) >= cap:
                    wait = int(window - (now - q[0])) + 1
                    return JSONResponse({"detail": "Too many requests. Slow down."}, 429, {"Retry-After": str(wait)})
                q.append(now)
            break  # most specific rule only
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(self), geolocation=()")
        return resp

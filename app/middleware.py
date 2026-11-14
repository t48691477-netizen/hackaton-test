import ipaddress
import math
import os
import threading
import time
from collections import OrderedDict, deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    trusted_proxy = os.getenv("TOIR_TRUSTED_PROXY_IP", "")
    if peer == trusted_proxy:
        forwarded = request.headers.get("x-real-ip", "").strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    try:
        return str(ipaddress.ip_address(peer))
    except ValueError:
        return "unknown"


class IngressRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 120, window_seconds: int = 60, max_clients: int = 10_000):
        super().__init__(app)
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self.max_clients = max(1, max_clients)
        self._requests: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def _retry_after(self, client_id: str) -> int | None:
        now = time.monotonic()
        with self._lock:
            while self._requests:
                _, oldest = next(iter(self._requests.items()))
                while oldest and now - oldest[0] >= self.window_seconds:
                    oldest.popleft()
                if oldest:
                    break
                self._requests.popitem(last=False)

            requests = self._requests.setdefault(client_id, deque())
            while requests and now - requests[0] >= self.window_seconds:
                requests.popleft()
            self._requests.move_to_end(client_id)

            if len(requests) >= self.limit:
                return max(1, math.ceil(self.window_seconds - (now - requests[0])))

            requests.append(now)
            while len(self._requests) > self.max_clients:
                self._requests.popitem(last=False)
            return None

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/health":
            return await call_next(request)

        client_id = client_ip(request)
        retry_after = self._retry_after(client_id)
        if retry_after is not None:
            return JSONResponse(
                {"detail": "Request rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)

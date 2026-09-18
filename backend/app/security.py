"""Local-first access policy for the browser-facing API.

This is not a user account system. It complements CORS (which only stops a
foreign page from *reading* responses) by rejecting browser requests that carry
an Origin we do not trust, so a random website cannot mutate local state either.
Non-browser clients (curl, tests, desktop launchers) send no Origin and pass.
"""
import os

from fastapi import Request
from fastapi.responses import JSONResponse

_LOCAL_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})


def _configured_origins() -> set:
    raw = os.environ.get("STORY_ENGINE_ALLOWED_ORIGINS", "")
    return {item.strip().rstrip("/") for item in raw.split(",") if item.strip()}


def _origin_hostname(origin: str) -> str:
    if "://" not in origin:
        return ""
    host = origin.split("://", 1)[1]
    host = host.split("/", 1)[0]
    if host.startswith("["):  # IPv6 literal, e.g. [::1]:5173
        return host[1:host.find("]")] if "]" in host else host
    return host.rsplit(":", 1)[0] if ":" in host else host


def is_origin_allowed(origin: str) -> bool:
    if not origin:
        return True  # no Origin header => not a browser cross-origin request
    normalized = origin.strip().rstrip("/")
    if normalized in _configured_origins():
        return True
    if "://" not in normalized:
        return False
    scheme = normalized.split("://", 1)[0].lower()
    if scheme not in ("http", "https"):
        return False
    return _origin_hostname(normalized).lower() in _LOCAL_HOSTNAMES


def allowed_origins_for_cors() -> list:
    configured = sorted(_configured_origins())
    if configured:
        return configured
    # Common local dev/preview ports. Requests from any other localhost port are
    # still accepted by the middleware below, but CORS echo needs a concrete list.
    return [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:8000", "http://127.0.0.1:8000",
    ]


async def local_origin_guard(request: Request, call_next):
    origin = request.headers.get("origin", "")
    if not is_origin_allowed(origin):
        return JSONResponse(
            status_code=403,
            content={"detail": "Origin not allowed for this local application."},
        )
    return await call_next(request)

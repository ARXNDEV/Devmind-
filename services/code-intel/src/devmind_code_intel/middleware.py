"""Internal-plane authentication.

Every request (except health probes) must present the shared service token.
This service is never exposed publicly; the token is defense-in-depth for
lateral movement inside the deployment network (08-security.md).
"""

import hmac

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import get_settings

_PUBLIC_PATHS = {"/healthz", "/readyz"}
_AUTH_HEADER = "x-internal-token"


class InternalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        expected = get_settings().internal_service_token.get_secret_value()
        presented = request.headers.get(_AUTH_HEADER, "")
        if not hmac.compare_digest(presented, expected):
            return JSONResponse(
                status_code=401,
                content={
                    "type": "about:blank",
                    "title": "Unauthorized",
                    "status": 401,
                    "detail": "Missing or invalid internal service token",
                },
                media_type="application/problem+json",
            )
        return await call_next(request)

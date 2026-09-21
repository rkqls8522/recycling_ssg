"""Request-ID + access-log middleware.

Every response carries an ``X-Request-ID`` header. If the client sends one
it is echoed back (and used in error bodies); otherwise the backend
generates a UUIDv4 (섹션 3.2).

This also logs every request/response pair (method, path, query string,
status code, duration, request id) so routing/404 issues are visible in
``.dev-logs/backend.log`` without needing to instrument each endpoint.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("api.access")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming.strip() if incoming and incoming.strip() else str(uuid.uuid4())
        request.state.request_id = request_id

        path = request.url.path
        query = f"?{request.url.query}" if request.url.query else ""
        client = request.client.host if request.client else "-"
        logger.info(
            "--> %s %s%s from %s [%s]", request.method, path, query, client, request_id
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "<-- %s %s%s raised an unhandled exception after %.1fms [%s]",
                request.method,
                path,
                query,
                duration_ms,
                request_id,
            )
            raise
        duration_ms = (time.perf_counter() - start) * 1000

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "<-- %s %s%s %d (%.1fms) [%s]",
            request.method,
            path,
            query,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response

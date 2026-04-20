# backend/app/api/middleware/rate_limiter.py
from starlette.middleware.base import (
    BaseHTTPMiddleware, RequestResponseEndpoint
)
from starlette.requests import Request
from starlette.responses import JSONResponse
import logging
import time

logger = logging.getLogger(__name__)

# Simple in-memory rate limiter for single-instance deployments
# Production: Use Redis-based rate limiting via CacheService
_request_counts: dict[str, list[float]] = {}

# Configuration
RATE_LIMIT_REQUESTS = 60  # Max requests per window
RATE_LIMIT_WINDOW = 60    # Window size in seconds

# Paths exempt from rate limiting
EXEMPT_PATHS = {"/health", "/api/docs", "/openapi.json"}


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Token-bucket-style rate limiter per user/IP.
    
    In production, this should use Azure Redis Cache for
    distributed rate limiting across Container Apps instances.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        # Identify client by user_id (from auth) or IP
        client_id = getattr(
            request.state, "user_id", None
        ) or request.client.host

        rate_key = f"rate:{client_id}"
        now = time.time()

        # Clean old entries and check count
        if rate_key not in _request_counts:
            _request_counts[rate_key] = []

        # Remove timestamps outside the window
        _request_counts[rate_key] = [
            ts for ts in _request_counts[rate_key]
            if now - ts < RATE_LIMIT_WINDOW
        ]

        if len(_request_counts[rate_key]) >= RATE_LIMIT_REQUESTS:
            logger.warning(
                f"Rate limit exceeded for client: {client_id}"
            )
            retry_after = int(
                RATE_LIMIT_WINDOW
                - (now - _request_counts[rate_key][0])
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please retry later.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        _request_counts[rate_key].append(now)

        # Add rate limit headers to response
        response = await call_next(request)
        remaining = RATE_LIMIT_REQUESTS - len(
            _request_counts[rate_key]
        )
        response.headers["X-RateLimit-Limit"] = str(
            RATE_LIMIT_REQUESTS
        )
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(
            int(now + RATE_LIMIT_WINDOW)
        )

        return response

# backend/app/api/middleware/__init__.py
"""Middleware components for the FastAPI application."""

from app.api.middleware.auth_middleware import AzureADAuthMiddleware
from app.api.middleware.rate_limiter import RateLimiterMiddleware
from app.api.middleware.error_handler import global_exception_handler

__all__ = [
    "AzureADAuthMiddleware",
    "RateLimiterMiddleware",
    "global_exception_handler",
]
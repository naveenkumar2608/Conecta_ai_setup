# backend/app/api/middleware/error_handler.py
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import traceback
import logging

logger = logging.getLogger(__name__)


async def global_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Global exception handler for all unhandled exceptions.
    
    - Logs full traceback for debugging
    - Returns sanitized error to client (no internal details)
    - Maps known exception types to appropriate HTTP status codes
    """
    # Handle Starlette/FastAPI HTTP exceptions
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "detail": exc.detail,
                "status_code": exc.status_code,
            },
        )

    # Handle ValueError (bad input)
    if isinstance(exc, ValueError):
        logger.warning(f"Validation error: {exc}")
        return JSONResponse(
            status_code=400,
            content={
                "error": True,
                "detail": str(exc),
                "status_code": 400,
            },
        )

    # Handle PermissionError
    if isinstance(exc, PermissionError):
        logger.warning(f"Permission denied: {exc}")
        return JSONResponse(
            status_code=403,
            content={
                "error": True,
                "detail": "Permission denied",
                "status_code": 403,
            },
        )

    # Handle all other exceptions
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {exc}\n"
        f"{traceback.format_exc()}"
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "detail": "An internal server error occurred. "
                      "Please try again later.",
            "status_code": 500,
            "request_id": getattr(
                request.state, "request_id", None
            ),
        },
    )

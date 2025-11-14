"""
Global exception handler middleware for FastAPI.

Catches all unhandled exceptions and logs them appropriately
while returning appropriate HTTP responses to clients.
"""

import logging
import sys
import traceback
from typing import Callable, Optional

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.

    Catches all unhandled exceptions, logs them,
    and returns appropriate HTTP responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and handle any exceptions.

        Args:
            request: FastAPI request object
            call_next: Next middleware/handler in chain

        Returns:
            Response from handler or error response
        """
        try:
            response = await call_next(request)
            return response

        except Exception as error:
            # Extract request context
            context = {
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "client_host": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", "unknown"),
            }

            # Add user ID if available (from auth)
            if hasattr(request.state, "user_id"):
                context["user_id"] = request.state.user_id

            # Add request ID if available
            if hasattr(request.state, "request_id"):
                context["request_id"] = request.state.request_id

            # Log error
            logger.error(
                f"Unhandled exception in {request.method} {request.url.path}",
                exc_info=True,
                extra=context,
            )

            # Determine HTTP status code
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

            # Determine error message (hide details in production)
            if settings.is_production:
                error_message = "An internal server error occurred. Please try again later."
                error_detail = None
            else:
                error_message = str(error)
                error_detail = {
                    "type": type(error).__name__,
                    "traceback": traceback.format_exc(),
                }

            # Return JSON error response
            return JSONResponse(
                status_code=status_code,
                content={
                    "success": False,
                    "error": error_message,
                    "detail": error_detail,
                    "request_id": context.get("request_id"),
                },
            )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers for FastAPI application.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Global exception handler for all unhandled exceptions.

        This catches exceptions not handled by other specific handlers.
        """
        # Extract request context
        context = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "client_host": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
        }

        # Add user ID if available
        if hasattr(request.state, "user_id"):
            context["user_id"] = request.state.user_id

        # Log error
        logger.error(
            f"Unhandled exception in {request.method} {request.url.path}",
            exc_info=True,
            extra=context,
        )

        # Determine error message
        if settings.is_production:
            error_message = "An internal server error occurred. Please try again later."
            error_detail = None
        else:
            error_message = str(exc)
            error_detail = {
                "type": type(exc).__name__,
                "traceback": traceback.format_exc(),
            }

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": error_message,
                "detail": error_detail,
                "request_id": context.get("request_id"),
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """
        Handler for ValueError exceptions (400 Bad Request).

        These are typically validation errors that should not trigger alerts.
        """
        logger.warning(f"ValueError in {request.method} {request.url.path}: {exc}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": str(exc),
                "type": "ValidationError",
            },
        )

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
        """
        Handler for KeyError exceptions (typically 400 or 404).

        These might indicate missing required fields or resources.
        Send notification but with lower priority.
        """
        context = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "error_type": "KeyError",
        }

        logger.error(f"KeyError in {request.method} {request.url.path}: {exc}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "error": f"Missing required field: {str(exc)}",
                "type": "KeyError",
            },
        )

    logger.info("Global exception handlers registered")


def setup_error_monitoring(app: FastAPI) -> None:
    """
    Setup comprehensive error monitoring for the application.

    Args:
        app: FastAPI application instance
    """
    # Add error handler middleware
    app.add_middleware(ErrorHandlerMiddleware)

    # Register exception handlers
    setup_exception_handlers(app)

    logger.info("Error monitoring initialized")

"""
Claude PR Review API - FastAPI Implementation
REST API for AI-powered PR code review via Claude
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from app.config import Config
from app.routes.health import router as health_router
from app.routes.review import router as review_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

SENSITIVE_FIELD_NAMES = {"anthropic_api_key", "api_key", "authorization", "token", "key"}

def console_log(message: str) -> None:
    """Print to stdout so deployed hosts show key events even without log config."""
    print(message, flush=True)

def redact_validation_errors(value):
    """Redact request validation details that may contain secrets."""
    if isinstance(value, dict):
        loc = [str(part).lower() for part in value.get("loc", [])]
        if "input" in value and any(part in SENSITIVE_FIELD_NAMES for part in loc):
            value = {**value, "input": "***"}
        return {
            key: "***" if str(key).lower() in SENSITIVE_FIELD_NAMES else redact_validation_errors(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_validation_errors(item) for item in value]
    return value

# Error status mapping (equivalent to ERROR_STATUS_MAP in JS)
ERROR_STATUS_MAP = {
    "VALIDATION": status.HTTP_400_BAD_REQUEST,
    "NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "DIFF_TOO_LARGE": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "ANTHROPIC_AUTH": status.HTTP_401_UNAUTHORIZED,
    "RATE_LIMITED": status.HTTP_429_TOO_MANY_REQUESTS,
    "ANTHROPIC_RATE_LIMITED": status.HTTP_429_TOO_MANY_REQUESTS,
    "GITHUB_AUTH": status.HTTP_503_SERVICE_UNAVAILABLE,
    "GITHUB_VALIDATION": status.HTTP_502_BAD_GATEWAY,
    "GITHUB_NETWORK": status.HTTP_502_BAD_GATEWAY,
    "ANTHROPIC_SERVER_ERROR": status.HTTP_502_BAD_GATEWAY,
    "ANTHROPIC_NETWORK": status.HTTP_502_BAD_GATEWAY,
    "ANTHROPIC_UNEXPECTED": status.HTTP_502_BAD_GATEWAY,
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    logger.info("Starting Claude PR Review API")
    yield
    logger.info("Shutting down Claude PR Review API")

# Create FastAPI app
app = FastAPI(
    title="Claude PR Review API",
    description="REST API for AI-powered PR code review via Claude",
    version=Config.VERSION,
    lifespan=lifespan
)

# Add middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = asyncio.get_event_loop().time()
    console_log(f"[request] start method={request.method} path={request.url.path}")
    logger.info(f"[request] {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        console_log(
            f"[request] done method={request.method} path={request.url.path} "
            f"status={response.status_code} duration_ms={duration_ms}"
        )
        return response
    except Exception as exc:
        duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
        error_code = getattr(exc, 'code', 'INTERNAL_ERROR')
        status_code = ERROR_STATUS_MAP.get(error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        console_log(
            f"[request] error method={request.method} path={request.url.path} "
            f"code={error_code} status={status_code} duration_ms={duration_ms} message={exc}"
        )
        logger.error(f"[request] error {error_code} ({status_code}): {exc}")

        return JSONResponse(
            status_code=status_code,
            content={
                "error": str(exc) or "Internal server error",
                "code": error_code,
            }
        )

# Include routers
app.include_router(health_router)
app.include_router(review_router)

# Global error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors that otherwise return 422 before route handlers run."""
    redacted_errors = redact_validation_errors(exc.errors())
    console_log(f"[validation] path={request.url.path} errors={redacted_errors}")
    logger.warning(f"[validation] {request.url.path}: {redacted_errors}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": redacted_errors,
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    error_code = getattr(exc, 'code', 'INTERNAL_ERROR')
    status_code = ERROR_STATUS_MAP.get(error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    console_log(f"[error] path={request.url.path} code={error_code} status={status_code} message={exc}")
    logger.error(f"[error] {error_code} ({status_code}): {exc}")

    if status_code >= 500:
        logger.error(exc.__traceback__)

    return JSONResponse(
        status_code=status_code,
        content={
            "error": str(exc) or "Internal server error",
            "code": error_code,
        }
    )

if __name__ == "__main__":
    port = int(os.getenv("PORT", 3000))
    logger.info(f"Claude PR Review API v{Config.VERSION} listening on port {port}")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        timeout_keep_alive=120,  # Give Claude enough time to respond on large diffs
    )

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
    logger.info(f"[request] {request.method} {request.url.path}")
    response = await call_next(request)
    return response

# Include routers
app.include_router(health_router)
app.include_router(review_router)

# Global error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    error_code = getattr(exc, 'code', 'INTERNAL_ERROR')
    status_code = ERROR_STATUS_MAP.get(error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

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
        reload=True,
        timeout_keep_alive=120,  # Give Claude enough time to respond on large diffs
    )
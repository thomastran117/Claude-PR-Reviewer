"""
Authentication middleware/dependencies
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from app.config import RuntimeConfig

security = HTTPBearer()

def authenticate_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Authenticate user based on API key
    Returns user dict with key and username
    """
    try:
        runtime_config = RuntimeConfig.load()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = credentials.credentials
    username = runtime_config.allowed_api_keys.get(api_key)

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"key": api_key, "username": username}
"""
Health check route
"""

from fastapi import APIRouter
from app.config import Config

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": Config.VERSION
    }
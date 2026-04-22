#!/usr/bin/env python3
"""
Simple smoke test to verify the FastAPI app imports and /health responds.
"""

import sys

from fastapi.testclient import TestClient

from main import app


def test_app():
    """Test the FastAPI application health endpoint."""
    print("Testing health endpoint...")

    response = TestClient(app).get("/health")

    if response.status_code == 200:
        data = response.json()
        print(f"Health check passed: {data}")
        return True

    print(f"Health check failed: {response.status_code} {response.text}")
    return False


if __name__ == "__main__":
    success = test_app()
    sys.exit(0 if success else 1)

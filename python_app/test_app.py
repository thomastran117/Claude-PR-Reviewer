#!/usr/bin/env python3
"""
Simple test script to verify the FastAPI app starts and health endpoint works
"""

import subprocess
import time
import requests
import sys
import os

def test_app():
    """Test the FastAPI application"""
    # Set minimal environment variables for testing
    env = os.environ.copy()
    env.update({
        'GITHUB_APP_ID': 'test',
        'GITHUB_APP_PRIVATE_KEY': 'test',
        'GITHUB_INSTALLATION_ID': '123',
        'ALLOWED_API_KEYS': '{"test":"testuser"}',
        'PORT': '3001'
    })

    # Start the app in background
    print("Starting FastAPI app...")
    process = subprocess.Popen(
        [sys.executable, 'main.py'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=os.path.dirname(__file__)
    )

    try:
        # Wait for app to start
        time.sleep(3)

        # Test health endpoint
        print("Testing health endpoint...")
        response = requests.get('http://localhost:3001/health', timeout=5)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False
    finally:
        # Clean up
        process.terminate()
        process.wait()

if __name__ == '__main__':
    success = test_app()
    sys.exit(0 if success else 1)
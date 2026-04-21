#!/usr/bin/env python3
"""
Development runner script for Claude PR Review API

This script loads environment variables from .env file and starts the FastAPI app.
"""

import os
import sys
from pathlib import Path

def load_env_file():
    """Load environment variables from .env file if it exists"""
    env_file = Path('.env')
    if env_file.exists():
        print("📄 Loading environment variables from .env file")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value
    else:
        print("⚠️  No .env file found. Make sure to create one from .env.example")

def main():
    """Run the FastAPI application"""
    print("🚀 Starting Claude PR Review API (Development)")

    # Load environment variables
    load_env_file()

    # Import and run the app
    try:
        from main import app
        import uvicorn

        port = int(os.getenv('PORT', 3000))
        print(f"🌐 Server will start on http://localhost:{port}")
        print(f"📊 Health check: http://localhost:{port}/health")
        print("Press Ctrl+C to stop")

        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=port,
            reload=True,
            log_level="info"
        )

    except ImportError as e:
        print(f"❌ Failed to import application: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
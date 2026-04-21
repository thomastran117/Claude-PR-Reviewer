#!/usr/bin/env python3
"""
Railway Deployment Helper Script

This script helps prepare the Python app for Railway deployment by:
1. Validating the environment variables
2. Testing the application locally
3. Providing deployment instructions

Usage:
    python deploy_to_railway.py
"""

import os
import sys
import json
import subprocess
from pathlib import Path

def check_environment_variables():
    """Check if required environment variables are set"""
    required_vars = [
        'GITHUB_APP_ID',
        'GITHUB_APP_PRIVATE_KEY',
        'GITHUB_INSTALLATION_ID',
        'ALLOWED_API_KEYS'
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file or Railway dashboard.")
        return False

    # Validate ALLOWED_API_KEYS is valid JSON
    try:
        api_keys = json.loads(os.getenv('ALLOWED_API_KEYS', '{}'))
        if not isinstance(api_keys, dict) or not api_keys:
            raise ValueError("ALLOWED_API_KEYS must be a non-empty JSON object")
    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ Invalid ALLOWED_API_KEYS: {e}")
        return False

    print("✅ All required environment variables are set")
    return True

def test_application():
    """Test if the application starts successfully"""
    print("🧪 Testing application startup...")

    try:
        # Set a test port to avoid conflicts
        env = os.environ.copy()
        env['PORT'] = '3001'

        # Start the app in background
        process = subprocess.Popen(
            [sys.executable, 'main.py'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=Path(__file__).parent
        )

        # Wait a bit for startup
        import time
        time.sleep(3)

        # Check if process is still running
        if process.poll() is None:
            print("✅ Application started successfully")
            process.terminate()
            process.wait()
            return True
        else:
            stdout, stderr = process.communicate()
            print("❌ Application failed to start")
            if stderr:
                print(f"Error: {stderr.decode()}")
            return False

    except Exception as e:
        print(f"❌ Error testing application: {e}")
        return False

def show_deployment_instructions():
    """Show Railway deployment instructions"""
    print("\n🚂 Railway Deployment Instructions:")
    print("=" * 50)
    print("1. Go to https://railway.app and click 'New Project'")
    print("2. Select 'Deploy from GitHub repo'")
    print("3. Choose this repository")
    print("4. Railway will auto-detect railway.toml and configure the build")
    print()
    print("5. Set these environment variables in Railway dashboard:")
    print("   - GITHUB_APP_ID")
    print("   - GITHUB_APP_PRIVATE_KEY")
    print("   - GITHUB_INSTALLATION_ID")
    print("   - ALLOWED_API_KEYS")
    print()
    print("6. Deploy and test with:")
    print("   curl https://your-app-name.railway.app/health")
    print("=" * 50)

def main():
    """Main deployment helper function"""
    print("🚀 Claude PR Review API - Railway Deployment Helper")
    print("=" * 55)

    # Check if we're in the right directory
    if not Path('main.py').exists():
        print("❌ Please run this script from the python_app directory")
        sys.exit(1)

    # Check environment variables
    if not check_environment_variables():
        sys.exit(1)

    # Test application
    if not test_application():
        sys.exit(1)

    # Show deployment instructions
    show_deployment_instructions()

    print("\n✅ Ready for Railway deployment!")
    print("Your Python FastAPI app is configured and tested.")

if __name__ == '__main__':
    main()
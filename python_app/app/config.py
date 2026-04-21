"""
Configuration module for Claude PR Review API
"""

import json
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass

# Load version from package.json equivalent (we'll create a pyproject.toml later)
VERSION = "1.0.0"

@dataclass
class RuntimeConfig:
    """Runtime configuration loaded from environment variables"""
    app_id: str
    private_key: str
    installation_id: int
    allowed_api_keys: Dict[str, str]

    @classmethod
    def load(cls) -> 'RuntimeConfig':
        """
        Validate business-logic env vars and return them, or raise an error.
        Called lazily so the server can always start and pass the /health check.
        """
        app_id = os.getenv('GITHUB_APP_ID')
        if not app_id:
            raise ValueError('Missing required env var: GITHUB_APP_ID')

        private_key = os.getenv('GITHUB_APP_PRIVATE_KEY')
        if not private_key:
            raise ValueError('Missing required env var: GITHUB_APP_PRIVATE_KEY')

        installation_id_str = os.getenv('GITHUB_INSTALLATION_ID')
        if not installation_id_str:
            raise ValueError('Missing required env var: GITHUB_INSTALLATION_ID')

        try:
            installation_id = int(installation_id_str)
        except ValueError:
            raise ValueError('GITHUB_INSTALLATION_ID must be a valid integer')

        raw_keys = os.getenv('ALLOWED_API_KEYS')
        if not raw_keys:
            raise ValueError('Missing required env var: ALLOWED_API_KEYS')

        try:
            allowed_api_keys = json.loads(raw_keys)
        except json.JSONDecodeError:
            raise ValueError('ALLOWED_API_KEYS must be valid JSON (e.g. {"key":"username"})')

        if not isinstance(allowed_api_keys, dict) or not allowed_api_keys:
            raise ValueError('ALLOWED_API_KEYS must be a non-empty JSON object')

        return cls(
            app_id=app_id,
            private_key=private_key.replace('\\n', '\n'),
            installation_id=installation_id,
            allowed_api_keys=allowed_api_keys
        )

class Config:
    """Application configuration"""
    VERSION = VERSION
    PORT = int(os.getenv("PORT", 3000))
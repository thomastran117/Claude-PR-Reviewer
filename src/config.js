'use strict';

const { version } = require('../package.json');

const rawPort = process.env.PORT;
const port = rawPort ? parseInt(rawPort, 10) : 3000;

// Validate business-logic env vars and return them, or return an error string.
// Called lazily so the server can always start and pass the /health check.
function loadRuntimeConfig() {
  const appId = process.env.GITHUB_APP_ID;
  if (!appId) return { error: 'Missing required env var: GITHUB_APP_ID' };

  const privateKey = process.env.GITHUB_APP_PRIVATE_KEY;
  if (!privateKey) return { error: 'Missing required env var: GITHUB_APP_PRIVATE_KEY' };

  const installationId = process.env.GITHUB_INSTALLATION_ID;
  if (!installationId) return { error: 'Missing required env var: GITHUB_INSTALLATION_ID' };

  const rawKeys = process.env.ALLOWED_API_KEYS;
  if (!rawKeys) {
    return { error: 'Missing required env var: ALLOWED_API_KEYS' };
  }

  let allowedApiKeys;
  try {
    allowedApiKeys = JSON.parse(rawKeys);
  } catch {
    return { error: 'ALLOWED_API_KEYS must be valid JSON (e.g. {"key":"username"})' };
  }

  if (
    typeof allowedApiKeys !== 'object' ||
    allowedApiKeys === null ||
    Array.isArray(allowedApiKeys)
  ) {
    return { error: 'ALLOWED_API_KEYS must be a JSON object' };
  }

  if (Object.keys(allowedApiKeys).length === 0) {
    return { error: 'ALLOWED_API_KEYS must contain at least one key' };
  }

  return { appId, privateKey: privateKey.replace(/\\n/g, '\n'), installationId: parseInt(installationId, 10), allowedApiKeys };
}

module.exports = { port, version, loadRuntimeConfig };

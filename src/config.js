'use strict';

const { version } = require('../package.json');

function validate() {
  const githubToken = process.env.GITHUB_TOKEN;
  if (!githubToken) {
    throw new Error('Missing required env var: GITHUB_TOKEN');
  }

  const rawKeys = process.env.ALLOWED_API_KEYS;
  if (!rawKeys) {
    throw new Error('Missing required env var: ALLOWED_API_KEYS');
  }

  let allowedApiKeys;
  try {
    allowedApiKeys = JSON.parse(rawKeys);
  } catch {
    throw new Error('ALLOWED_API_KEYS must be valid JSON (e.g. {"key":"username"})');
  }

  if (
    typeof allowedApiKeys !== 'object' ||
    allowedApiKeys === null ||
    Array.isArray(allowedApiKeys)
  ) {
    throw new Error('ALLOWED_API_KEYS must be a JSON object');
  }

  if (Object.keys(allowedApiKeys).length === 0) {
    throw new Error('ALLOWED_API_KEYS must contain at least one key');
  }

  const rawPort = process.env.PORT;
  const port = rawPort ? parseInt(rawPort, 10) : 3000;
  if (!Number.isFinite(port) || port <= 0) {
    throw new Error(`Invalid PORT value: "${rawPort}"`);
  }

  return { githubToken, allowedApiKeys, port, version };
}

module.exports = validate();

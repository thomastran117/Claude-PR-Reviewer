'use strict';

const { loadRuntimeConfig } = require('../config');

function auth(req, res, next) {
  const header = req.headers['authorization'];

  if (!header || !header.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing or malformed Authorization header' });
  }

  const key = header.slice(7);
  const runtimeConfig = loadRuntimeConfig();

  if (runtimeConfig.error) {
    return res.status(503).json({ error: runtimeConfig.error, code: 'MISCONFIGURED' });
  }

  const username = runtimeConfig.allowedApiKeys[key];

  if (!username) {
    return res.status(401).json({ error: 'Invalid API key' });
  }

  req.user = { key, username };
  next();
}

module.exports = auth;

'use strict';

const config = require('../config');

function auth(req, res, next) {
  const header = req.headers['authorization'];

  if (!header || !header.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing or malformed Authorization header' });
  }

  const key = header.slice(7);
  const username = config.allowedApiKeys[key];

  if (!username) {
    return res.status(401).json({ error: 'Invalid API key' });
  }

  req.user = { key, username };
  next();
}

module.exports = auth;

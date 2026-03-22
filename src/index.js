'use strict';

const config = require('./config');

const express = require('express');
const healthRouter = require('./routes/health');
const reviewRouter = require('./routes/review');

const app = express();

app.use(express.json({ limit: '1mb' }));

// Request logging
app.use((req, _res, next) => {
  console.log(`[request] ${req.method} ${req.path}`);
  next();
});

// Routes
app.use(healthRouter);
app.use(reviewRouter);

// Global error handler
const ERROR_STATUS_MAP = {
  VALIDATION: 400,
  NOT_FOUND: 404,
  DIFF_TOO_LARGE: 422,
  ANTHROPIC_AUTH: 401,       // caller passed a bad Anthropic key
  RATE_LIMITED: 429,
  ANTHROPIC_RATE_LIMITED: 429,
  GITHUB_AUTH: 503,          // server's own GitHub token is misconfigured
  GITHUB_VALIDATION: 502,
  GITHUB_NETWORK: 502,
  ANTHROPIC_SERVER_ERROR: 502,
  ANTHROPIC_NETWORK: 502,
  ANTHROPIC_UNEXPECTED: 502,
};

// eslint-disable-next-line no-unused-vars
app.use((err, _req, res, _next) => {
  const status = ERROR_STATUS_MAP[err.code] ?? 500;
  console.error(`[error] ${err.code ?? 'UNKNOWN'} (${status}): ${err.message}`);
  if (status >= 500) console.error(err.stack);
  res.status(status).json({
    error: err.message || 'Internal server error',
    code: err.code || 'INTERNAL_ERROR',
  });
});

const server = app.listen(config.port, () => {
  console.log(`Claude PR Review API v${config.version} listening on port ${config.port}`);
});

// Give Claude enough time to respond on large diffs
server.setTimeout(120_000);

module.exports = app;

'use strict';

// Validate env vars before anything else — throws synchronously if invalid
const config = require('./config');

const express = require('express');
const healthRouter = require('./routes/health');
const reviewRouter = require('./routes/review');

const app = express();

app.use(express.json({ limit: '1mb' }));

// Routes
app.use(healthRouter);
app.use(reviewRouter);

// Global error handler
const ERROR_STATUS_MAP = {
  NOT_FOUND: 404,
  DIFF_TOO_LARGE: 422,
  RATE_LIMITED: 429,
  ANTHROPIC_RATE_LIMITED: 429,
  GITHUB_AUTH: 502,
  GITHUB_VALIDATION: 502,
  GITHUB_NETWORK: 502,
  ANTHROPIC_AUTH: 502,
  ANTHROPIC_SERVER_ERROR: 502,
  ANTHROPIC_NETWORK: 502,
  ANTHROPIC_UNEXPECTED: 502,
  VALIDATION: 400,
};

// eslint-disable-next-line no-unused-vars
app.use((err, _req, res, _next) => {
  const status = ERROR_STATUS_MAP[err.code] ?? 500;
  console.error(`[error] ${err.code ?? 'UNKNOWN'} (${status}): ${err.message}`);
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

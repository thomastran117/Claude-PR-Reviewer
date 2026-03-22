'use strict';

const { Router } = require('express');
const config = require('../config');

const router = Router();

router.get('/health', (_req, res) => {
  res.json({ status: 'ok', version: config.version });
});

module.exports = router;

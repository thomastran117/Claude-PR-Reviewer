'use strict';

const Anthropic = require('@anthropic-ai/sdk');

function makeError(code, message) {
  const err = new Error(message);
  err.code = code;
  return err;
}

async function review(systemPrompt, userMessage, anthropicApiKey) {
  const client = new Anthropic({ apiKey: anthropicApiKey });

  let msg;
  try {
    msg = await client.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 2048,
      system: systemPrompt,
      messages: [{ role: 'user', content: userMessage }],
    });
  } catch (err) {
    if (err instanceof Anthropic.AuthenticationError) {
      throw makeError('ANTHROPIC_AUTH', 'Anthropic API key is invalid or missing');
    }
    if (err instanceof Anthropic.RateLimitError) {
      throw makeError('ANTHROPIC_RATE_LIMITED', 'Anthropic rate limit hit. Try again shortly.');
    }
    if (err instanceof Anthropic.APIConnectionError) {
      throw makeError('ANTHROPIC_NETWORK', 'Cannot reach Anthropic API');
    }
    if (err instanceof Anthropic.APIError) {
      throw makeError('ANTHROPIC_SERVER_ERROR', `Anthropic API error: ${err.status} ${err.message}`);
    }
    throw makeError('ANTHROPIC_NETWORK', `Unexpected error calling Anthropic: ${err.message}`);
  }

  const text = msg?.content?.[0]?.text;
  if (typeof text !== 'string') {
    throw makeError('ANTHROPIC_UNEXPECTED', 'Anthropic returned an unexpected response shape');
  }

  return text.trim();
}

module.exports = { review };

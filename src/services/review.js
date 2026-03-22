'use strict';

const fs = require('fs');
const path = require('path');

const SYSTEM_PROMPT = fs.readFileSync(
  path.join(__dirname, '../../prompts/system.md'),
  'utf8'
);

const FALLBACK_REVIEW =
  'STATUS: OK\n\n' +
  '## Summary\nCould not generate a review.\n\n' +
  '## Mandatory 🔴\nNone.\n\n' +
  '## Suggestions 🟡\nNone.\n\n' +
  '## Nitpicks 🟢\nNone.\n\n' +
  '## Stack-Specific Notes\nNot applicable for this diff.\n\n' +
  '## Inline Annotations\n[]';

function buildUserPrompt(prData) {
  const { title, author, pull_number, body, diffSummary, files } = prData;

  const description = body ? body.slice(0, 5000) + (body.length > 5000 ? '\n\n_(Description truncated.)_' : '') : '(No description provided)';

  let prompt =
    `PR Title: ${title}\n` +
    `PR Author: ${author}\n` +
    `PR Number: #${pull_number}\n\n` +
    `PR Description:\n${description}\n\n` +
    `Changed files (showing up to 30):\n\n` +
    diffSummary;

  const filesWithContent = files.filter(f => f.fullContent);
  if (filesWithContent.length > 0) {
    prompt += '\n\n---\n## Full File Contents\n';
    for (const f of filesWithContent) {
      const ext = f.filename.split('.').pop() || '';
      prompt += `\n### ${f.filename}\n\`\`\`${ext}\n${f.fullContent}\n\`\`\`\n`;
    }
  }

  return prompt;
}

function parseStatus(reviewText) {
  const match = reviewText.match(/^STATUS:\s*(PASS|OK|FAIL)\s*$/m);
  return match ? match[1] : 'UNKNOWN';
}

function parseInlineComments(reviewText) {
  try {
    const sectionMatch = reviewText.match(/## Inline Annotations\s*([\s\S]*?)(?:\n##|$)/);
    if (!sectionMatch) {
      console.warn('[review] No ## Inline Annotations section found in review output');
      return [];
    }

    const content = sectionMatch[1].trim();
    console.log(`[review] Inline annotations raw content: ${content.slice(0, 300)}`);
    if (!content || content === '[]') return [];

    // Strip code fences if present
    const jsonStr = content.replace(/^```(?:json)?\s*/m, '').replace(/\s*```$/m, '').trim();

    const parsed = JSON.parse(jsonStr);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(item =>
      typeof item.path === 'string' &&
      typeof item.line === 'number' &&
      Number.isFinite(item.line) &&
      item.line > 0 &&
      typeof item.body === 'string' &&
      item.body.length > 0
    );
  } catch (err) {
    console.warn('[review] Failed to parse inline annotations:', err.message);
    return [];
  }
}

module.exports = { SYSTEM_PROMPT, FALLBACK_REVIEW, buildUserPrompt, parseStatus, parseInlineComments };

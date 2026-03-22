'use strict';

const { Router } = require('express');
const auth = require('../middleware/auth');
const githubService = require('../services/github');
const claudeService = require('../services/claude');
const reviewService = require('../services/review');

const router = Router();

const PR_URL_REGEX = /github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/;

router.post('/api/review', auth, async (req, res, next) => {
  const startTime = Date.now();
  const body = req.body || {};

  const { anthropic_api_key, pr_url, owner: rawOwner, repo: rawRepo, pull_number: rawPullNumber, post_comment } = body;

  if (!anthropic_api_key || typeof anthropic_api_key !== 'string' || !anthropic_api_key.trim()) {
    return res.status(400).json({ error: 'Missing required field: anthropic_api_key' });
  }

  let owner, repo, pull_number;

  if (pr_url) {
    const match = String(pr_url).match(PR_URL_REGEX);
    if (!match) {
      return res.status(400).json({ error: 'Invalid pr_url format. Expected: https://github.com/owner/repo/pull/123' });
    }
    [, owner, repo] = match;
    pull_number = parseInt(match[3], 10);
  } else if (rawOwner && rawRepo && rawPullNumber != null) {
    owner = String(rawOwner).trim();
    repo = String(rawRepo).trim();
    pull_number = parseInt(rawPullNumber, 10);

    if (!owner || !repo) {
      return res.status(400).json({ error: 'owner and repo must be non-empty strings' });
    }
    if (!Number.isFinite(pull_number) || pull_number <= 0) {
      return res.status(400).json({ error: 'pull_number must be a positive integer' });
    }
  } else {
    return res.status(400).json({ error: 'Must provide pr_url OR owner + repo + pull_number' });
  }

  const shouldPostComment = post_comment === true || post_comment === 'true';

  const pr = `${owner}/${repo}#${pull_number}`;
  console.log(`[review] start ${pr} user=${req.user.username} post_comment=${shouldPostComment}`);

  try {
    // 1. Fetch PR data
    console.log(`[review] fetching PR data for ${pr}`);
    const prData = await githubService.getPRData(owner, repo, pull_number);
    console.log(`[review] fetched ${prData.files_reviewed} files, ${prData.total_diff_chars} chars`);

    // 2. Build prompt
    const userMessage = reviewService.buildUserPrompt(prData);

    // 3. Call Claude
    console.log(`[review] calling Claude`);
    let reviewText = await claudeService.review(reviewService.SYSTEM_PROMPT, userMessage, anthropic_api_key);
    if (!reviewText) reviewText = reviewService.FALLBACK_REVIEW;
    console.log(`[review] Claude responded`);

    // 4. Parse results
    const status = reviewService.parseStatus(reviewText);
    const inlineComments = reviewService.parseInlineComments(reviewText);
    console.log(`[review] status=${status} inline_comments=${inlineComments.length}`);

    // 5. Optionally post to GitHub
    let commentPosted = false;
    let reviewId = null;
    let inlineCommentsPosted = 0;

    if (shouldPostComment) {
      console.log(`[review] posting comment to ${pr}`);
      await githubService.deletePreviousBotComments(owner, repo, pull_number);
      const result = await githubService.postReview(owner, repo, pull_number, prData.headSha, reviewText, inlineComments);
      commentPosted = true;
      reviewId = result.review_id;
      inlineCommentsPosted = result.inline_comments_posted;
      console.log(`[review] posted review_id=${reviewId} inline_comments=${inlineCommentsPosted}`);
    }

    console.log(`[review] done ${pr} duration=${Date.now() - startTime}ms`);
    res.json({
      status,
      review: reviewText,
      inline_comments: inlineComments,
      metadata: {
        pr_url: prData.pr_url,
        pr_title: prData.title,
        files_reviewed: prData.files_reviewed,
        files_truncated: prData.files_truncated,
        total_diff_chars: prData.total_diff_chars,
        comment_posted: commentPosted,
        review_id: reviewId,
        inline_comments_posted: inlineCommentsPosted,
        username: req.user.username,
        duration_ms: Date.now() - startTime,
      },
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;

# Claude PR Review API

A self-hosted REST API that reviews GitHub pull requests using Claude (Anthropic). Reviews are posted as a GitHub App bot, keeping them clearly separate from your personal account. Inline code annotations are posted as individual line comments alongside a summary review.

Targeted at **Angular**, **.NET**, and **Node.js (serverless)** stacks.

---

## How it works

1. A caller (GitHub Actions, CI, or direct API call) sends a PR URL + their Anthropic API key
2. The server fetches the PR diff from GitHub
3. Claude reviews the diff at principal/staff engineer level
4. The review is posted to the PR via a GitHub App bot (`your-app[bot]`)
   - A summary comment with status (PASS / OK / FAIL) and findings
   - Individual inline annotations on specific changed lines

> **No Anthropic key is stored on the server.** Each caller supplies their own.

---

## Endpoints

### `GET /health`
Returns server status.

```json
{ "status": "ok", "version": "1.0.0" }
```

### `POST /api/review`

**Headers:**
```
Authorization: Bearer <api-key>
Content-Type: application/json
```

**Body:**
```json
{
  "anthropic_api_key": "sk-ant-...",
  "pr_url": "https://github.com/owner/repo/pull/123",
  "post_comment": true
}
```

Or use `owner` / `repo` / `pull_number` instead of `pr_url`. Set `post_comment: false` to get the review without posting to GitHub.

**Response:**
```json
{
  "status": "PASS",
  "review": "STATUS: PASS\n\n## Summary\n...",
  "inline_comments": [
    { "path": "src/foo.ts", "line": 42, "body": "Consider handling the null case here." }
  ],
  "metadata": {
    "pr_url": "https://github.com/owner/repo/pull/42",
    "pr_title": "Add feature X",
    "files_reviewed": 5,
    "files_truncated": false,
    "total_diff_chars": 12400,
    "comment_posted": true,
    "review_id": 1234567890,
    "inline_comments_posted": 3,
    "username": "alice",
    "duration_ms": 8312
  }
}
```

---

## Authentication

The API uses static bearer tokens configured via the `ALLOWED_API_KEYS` environment variable — a JSON map of token → username:

```json
{"your-secret-key-1": "alice", "your-secret-key-2": "ci-bot"}
```

Generate tokens with `openssl rand -hex 32`.

---

## GitHub Actions

To trigger reviews automatically, add three secrets to your repository (**Settings → Secrets and variables → Actions**):

| Secret | Value |
|---|---|
| `CLAUDE_REVIEW_API_URL` | Your deployed API URL |
| `CLAUDE_REVIEW_API_KEY` | One of the keys from `ALLOWED_API_KEYS` |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |

Copy `.github/workflows/ai-pr-review-api.yml` into the target repository. Reviews are triggered by adding the `ai-review` label to a pull request.

---

## Customising the prompt

The review prompt is in [`prompts/system.md`](prompts/system.md). Edit and push — Railway redeploys automatically.

---

## Deploying

See [DEPLOY.md](DEPLOY.md) for full Railway + GitHub App setup instructions.

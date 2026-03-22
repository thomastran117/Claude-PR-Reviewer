# Deploying to Railway

## Prerequisites

- A [Railway](https://railway.app) account
- A GitHub personal access token (PAT)
- An Anthropic API key (given to callers — not stored on the server)

---

## 1. Create a Railway project

1. Go to [railway.app](https://railway.app) and click **New Project**
2. Select **Deploy from GitHub repo**
3. Authorize Railway and select this repository
4. Railway will detect `railway.toml` and configure the build automatically

---

## 2. Set environment variables

In Railway, go to your service → **Variables** tab and add:

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` | A GitHub PAT used to fetch PR data and post review comments |
| `ALLOWED_API_KEYS` | JSON map of API keys to usernames (see below) |

**`GITHUB_TOKEN` permissions required:**

- If you only need to fetch PR data (no `post_comment`): `pull_requests: read`, `contents: read`
- If callers will use `post_comment: true`: also add `pull_requests: write`

A fine-grained PAT scoped to specific repositories is recommended over a classic token.

**`ALLOWED_API_KEYS` format:**

```json
{"your-secret-key-1":"alice","your-secret-key-2":"bob"}
```

Use a random string for each key (e.g. output of `openssl rand -hex 32`).

> **Note:** No `ANTHROPIC_API_KEY` is stored on the server. Each caller supplies their own Anthropic key in the request body.

---

## 3. Deploy

Railway deploys automatically on every push to your default branch. To trigger a manual deploy, go to **Deployments** and click **Deploy Now**.

Once deployed, your service URL will look like:
```
https://your-app-name.railway.app
```

Check that it's live:
```bash
curl https://your-app-name.railway.app/health
# → {"status":"ok","version":"1.0.0"}
```

---

## 4. Set up the GitHub Actions workflow

Add these three secrets to any repository where you want AI reviews (**Settings → Secrets and variables → Actions**):

| Secret | Value |
|---|---|
| `CLAUDE_REVIEW_API_URL` | Your Railway URL, e.g. `https://your-app-name.railway.app` |
| `CLAUDE_REVIEW_API_KEY` | One of the keys from your `ALLOWED_API_KEYS` map |
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |

Then copy `.github/workflows/ai-pr-review-api.yml` into the target repository.

To trigger a review, add the `ai-review` label to any non-draft pull request.

---

## Calling the API directly

```bash
curl -X POST https://your-app-name.railway.app/api/review \
  -H "Authorization: Bearer your-secret-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "anthropic_api_key": "sk-ant-...",
    "pr_url": "https://github.com/owner/repo/pull/123",
    "post_comment": true
  }'
```

Or using `owner` / `repo` / `pull_number` fields instead of `pr_url`:

```bash
curl -X POST https://your-app-name.railway.app/api/review \
  -H "Authorization: Bearer your-secret-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "anthropic_api_key": "sk-ant-...",
    "owner": "my-org",
    "repo": "my-repo",
    "pull_number": 42,
    "post_comment": false
  }'
```

**Response:**
```json
{
  "status": "PASS",
  "review": "STATUS: PASS\n\n## Summary\n...",
  "inline_comments": [
    { "path": "src/foo.js", "line": 42, "body": "Consider handling the null case here." }
  ],
  "metadata": {
    "pr_url": "https://github.com/owner/repo/pull/42",
    "pr_title": "Add feature X",
    "files_reviewed": 5,
    "files_truncated": false,
    "total_diff_chars": 12400,
    "comment_posted": false,
    "review_id": null,
    "inline_comments_posted": 0,
    "username": "alice",
    "duration_ms": 8312
  }
}
```

---

## Customising the review prompt

The system prompt Claude uses is stored in [`prompts/system.md`](prompts/system.md). Edit that file to change the review style, add new sections, or adjust the rules. No code changes required — just push the updated file and Railway will redeploy.

---

## Troubleshooting

**`401 Unauthorized`** — The `Authorization: Bearer <key>` header is missing or the key isn't in `ALLOWED_API_KEYS`.

**`400 Bad Request`** — Missing `anthropic_api_key`, invalid `pr_url`, or missing `owner`/`repo`/`pull_number`.

**`404 Not Found`** — The PR doesn't exist or `GITHUB_TOKEN` can't see it (check repo access).

**`422 Unprocessable Entity`** — The diff is too large to review (> 90,000 chars). Consider breaking the PR into smaller pieces.

**`502 Bad Gateway`** — An upstream call to GitHub or Anthropic failed. Check Railway logs for details (`railway logs`).

**Reviews not posting to GitHub** — Ensure `GITHUB_TOKEN` has `pull_requests: write` and the PR is not from a fork owned by a user without write access.

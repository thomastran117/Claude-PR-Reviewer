# Deploying to Railway

## Prerequisites

- A [Railway](https://railway.app) account
- A GitHub App (see step 2 below for setup)
- An Anthropic API key (given to callers — not stored on the server)

---

## 1. Create a Railway project

1. Go to [railway.app](https://railway.app) and click **New Project**
2. Select **Deploy from GitHub repo**
3. Authorize Railway and select this repository
4. Railway will detect `railway.toml` and configure the build automatically

---

## 2. Create a GitHub App

Reviews are posted by a GitHub App, so they appear as `your-app[bot]` rather than your personal account.

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**
2. Fill in:
   - **GitHub App name**: e.g. `MyOrg PR Reviewer`
   - **Homepage URL**: your Railway URL (can be filled in after deploy)
   - **Webhooks**: uncheck **Active** — not needed
   - **Repository permissions**:
     - `Pull requests`: Read & Write
     - `Contents`: Read-only
3. Click **Create GitHub App** and note the **App ID** shown on the settings page
4. Scroll down → **Generate a private key** → a `.pem` file will download
5. Go to the **Install App** tab → install it on the repositories you want reviewed
6. After installing, the URL will contain the **Installation ID**: `github.com/settings/installations/XXXXXXX`

---

## 3. Set environment variables

In Railway, go to your service → **Variables** tab and add:

| Variable | Description |
|---|---|
| `GITHUB_APP_ID` | Numeric App ID from step 2 |
| `GITHUB_APP_PRIVATE_KEY` | Full contents of the downloaded `.pem` file |
| `GITHUB_INSTALLATION_ID` | Numeric Installation ID from step 2 |
| `ALLOWED_API_KEYS` | JSON map of API keys to usernames (see below) |

For `GITHUB_APP_PRIVATE_KEY`, paste the raw PEM content including the `-----BEGIN RSA PRIVATE KEY-----` header and footer. Railway preserves newlines correctly.

**`ALLOWED_API_KEYS` format:**

```json
{"your-secret-key-1":"alice","your-secret-key-2":"bob"}
```

Use a random string for each key (e.g. output of `openssl rand -hex 32`).

> **Note:** No `ANTHROPIC_API_KEY` is stored on the server. Each caller supplies their own Anthropic key in the request body.

---

## 4. Deploy

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

## 5. Set up the GitHub Actions workflow

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

**`404 Not Found`** — The PR doesn't exist or the GitHub App can't see it. Ensure the app is installed on the repository.

**`422 Unprocessable Entity`** — The diff is too large to review (> 90,000 chars). Consider breaking the PR into smaller pieces.

**`502 Bad Gateway`** — An upstream call to GitHub or Anthropic failed. Check Railway logs for details (`railway logs`).

**Reviews not posting to GitHub** — Ensure the GitHub App has `Pull requests: Read & Write` permission and is installed on the target repository.

# Claude PR Review API (Python/FastAPI)

A REST API for AI-powered GitHub pull request code review using Claude AI.

## Features

- 🤖 AI-powered code review using Claude
- 🔐 GitHub App authentication
- 📝 Automatic PR comment posting
- 💾 In-memory LRU caching
- 🚀 FastAPI-based REST API
- 🐳 Docker support
- 🚂 Railway deployment ready

## Prerequisites

- Python 3.8+
- GitHub App with repository permissions
- Anthropic API key

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd python_app
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your values
```

4. Run the application:
```bash
# For development (with auto-reload and .env loading)
python dev.py

# Or directly
python main.py
```

Or use the deployment helper:
```bash
python deploy_to_railway.py  # Validates setup and shows deployment instructions
```

## Railway Deployment

### 1. Prepare for Deployment

The `python_app` directory is configured for easy Railway deployment:

- `railway.toml` - Railway configuration
- `requirements.txt` - Python dependencies
- `pyproject.toml` - Project metadata
- `Dockerfile` - Containerization (optional)
- `deploy_to_railway.py` - Deployment helper script

### 2. Validate Your Setup

Before deploying, run the deployment helper:

```bash
python deploy_to_railway.py
```

This will:
- ✅ Validate environment variables
- 🧪 Test application startup
- 📋 Show deployment instructions

### 3. Deploy to Railway

1. Go to [railway.app](https://railway.app) and click **New Project**
2. Select **Deploy from GitHub repo**
3. Authorize Railway and select your repository
4. Railway will detect `railway.toml` and configure the build automatically

### 4. Set Environment Variables

In Railway, go to your service → **Variables** tab and add:

| Variable | Description |
|---|---|
| `GITHUB_APP_ID` | Numeric App ID from GitHub App |
| `GITHUB_APP_PRIVATE_KEY` | Full contents of the downloaded `.pem` file |
| `GITHUB_INSTALLATION_ID` | Numeric Installation ID from GitHub App |
| `ALLOWED_API_KEYS` | JSON map of API keys to usernames |

### 5. Verify Deployment

Once deployed, check that it's live:
```bash
curl https://your-app-name.railway.app/health
# → {"status":"ok","version":"1.0.0"}
```

## API Endpoints

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0"
}
```

### POST /api/review
Review a GitHub pull request.

**Headers:**
```
Authorization: Bearer <api-key>
Content-Type: application/json
```

**Request Body:**
```json
{
  "anthropic_api_key": "your-anthropic-key",
  "pr_url": "https://github.com/owner/repo/pull/123",
  "post_comment": true
}
```

Or alternatively:
```json
{
  "anthropic_api_key": "your-anthropic-key",
  "owner": "owner",
  "repo": "repo",
  "pull_number": 123,
  "post_comment": false
}
```

**Response:**
```json
{
  "status": "PASS|OK|FAIL",
  "review": "Full review text...",
  "inline_comments": [],
  "metadata": {
    "pr_url": "https://github.com/owner/repo/pull/123",
    "pr_title": "PR Title",
    "files_reviewed": 5,
    "files_truncated": 0,
    "total_diff_chars": 1234,
    "comment_posted": true,
    "review_id": 12345,
    "inline_comments_posted": 0,
    "username": "reviewer",
    "duration_ms": 2500,
    "cached": false
  }
}
```

## Configuration

### Environment Variables

- `GITHUB_APP_ID`: GitHub App ID
- `GITHUB_APP_PRIVATE_KEY`: GitHub App private key (with newlines as `\n`)
- `GITHUB_INSTALLATION_ID`: GitHub App installation ID
- `ALLOWED_API_KEYS`: JSON object mapping API keys to usernames
- `PORT`: Server port (default: 3000)

## Migration from Node.js

This Python/FastAPI version is a complete rewrite of the original Node.js/Express application. Key differences:

- **Framework**: FastAPI instead of Express
- **Language**: Python instead of JavaScript
- **Dependencies**: Anthropic SDK, PyGithub instead of @anthropic-ai/sdk, @octokit
- **Async/Await**: Native Python async support
- **Type Safety**: Pydantic models for request/response validation

The API interface remains the same for backward compatibility.

## Docker

Build and run with Docker:

```bash
docker build -t claude-pr-review .
docker run -p 3000:3000 --env-file .env claude-pr-review
```

## License

MIT

# YouTube Transcript to Article
[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/W7W51C9X4H)

Turn spoken YouTube content into structured **Markdown** you can publish, quote, or refine further. The web app and HTTP API send captions (and optional metadata) through an **OpenAI-compatible** chat model—**OpenAI** or **LocalAI**—so you control depth, length, language, and model from one place. The same container can also run as an **MCP server** that returns **transcript and video description only**, so your assistant writes the article and no API key is required inside the MCP process.

## Features

- **Transcripts**: Resolves a video from a URL or ID, fetches captions, and trims very long text to protect context limits.
- **Depth levels**: Brief, standard, detailed, or comprehensive instructions to the model (legacy `summary` / `detailed` still accepted).
- **Word-target summary**: Optional “approximately N words” constraint (about ±10%) for tight summaries.
- **Model choice**: Per-request or default model name (e.g. `gpt-4o-mini`).
- **Host choice**: OpenAI, or LocalAI (any OpenAI-compatible server) via base URL.
- **Web UI**: Simple form at `/` with the same options as the API.
- **MCP server**: Same image can run as a [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes **transcript and/or video description/metadata only** (no LLM in the container).

## Requirements

- Docker (optional) or Python 3.10+
- An API key for OpenAI, or a LocalAI instance that does not require a real key (configure as needed)

## Configuration (environment variables)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for OpenAI (required when using `model_host: openai`). |
| `DEFAULT_MODEL` | Default model id if the client omits `model` (default: `gpt-4o-mini`). |
| `DEFAULT_MODEL_HOST` | Default host if the client omits `model_host`: `openai` or `localai` (default: `openai`). |
| `OPENAI_BASE_URL` | Optional override for OpenAI-compatible endpoints (must end with `/v1` or a path that resolves to the v1 API), e.g. proxies. |
| `LOCALAI_BASE_URL` | Base URL for LocalAI (default: `http://localhost:8080/v1`). Used when `model_host` is `localai`. |
| `LOCALAI_API_KEY` | Optional; falls back to `OPENAI_API_KEY` or a placeholder if unset. |
| `OPENAI_TIMEOUT` | Seconds for model requests (default: `180`). |
| `HTTP_REQUEST_TIMEOUT` | Seconds for scraping YouTube metadata (default: `30`). |
| `MAX_TRANSCRIPT_CHARS` | Hard cap on transcript length sent to the model (default: `120000`). |

### MCP (Model Context Protocol) environment

The MCP server **does not** call OpenAI or any other LLM. It only returns YouTube **captions** and/or **title, channel, and description** from the watch page so the **host assistant** can draft an article or summary. **No `OPENAI_API_KEY` is required** for MCP.

| Variable | Description |
|----------|-------------|
| `APP_MODE` | In Docker: `flask` (default) for the web app, or `mcp` to run [`mcp_server.py`](mcp_server.py). |
| `MCP_TRANSPORT` | `stdio` (default when running `python mcp_server.py` locally) or `streamable-http` for HTTP. In Docker, the entrypoint sets `streamable-http` when `APP_MODE=mcp` unless you override. |
| `FASTMCP_HOST` / `FASTMCP_PORT` | Bind address and port for streamable HTTP (defaults: `0.0.0.0` / `8000` when `MCP_TRANSPORT=streamable-http` at process start). |
| `MCP_HTTP_HOST` / `MCP_HTTP_PORT` | Aliases read by the MCP server if you prefer these names. |

Set `MCP_TRANSPORT` **before** starting Python so the listen address is applied correctly (e.g. `export MCP_TRANSPORT=streamable-http` then `python mcp_server.py`).

**Tools**

- `get_youtube_transcript` — caption text plus `video_title`, `video_description`, and `channel` (JSON string).
- `get_youtube_video_description` — title, channel, and description from the watch page only (no captions API; useful if transcripts are disabled).

**Local (stdio)**

```bash
python mcp_server.py
```

**Local (HTTP)** — MCP Inspector / streamable HTTP clients:

```bash
export MCP_TRANSPORT=streamable-http
python mcp_server.py
# Endpoint (default path): http://127.0.0.1:8000/mcp
```

**Docker (streamable HTTP)**

```bash
docker run --rm -p 8000:8000 \
  -e APP_MODE=mcp \
  ghcr.io/your-org/youtube-transcript-to-article:latest
```

Point your MCP client at `http://localhost:8000/mcp` (or your host) if it supports streamable HTTP.

**Docker (stdio)** — `-i` attaches stdin:

```bash
docker run --rm -i -e APP_MODE=mcp -e MCP_TRANSPORT=stdio ghcr.io/your-org/youtube-transcript-to-article:latest
```

**Cursor** — `stdio` via Docker (`-i` required):

```json
{
  "mcpServers": {
    "youtube-transcript": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "APP_MODE=mcp",
        "-e", "MCP_TRANSPORT=stdio",
        "ghcr.io/your-org/youtube-transcript-to-article:latest"
      ]
    }
  }
}
```

## Docker

```bash
# Docker Hub (replace with your namespace if different)
docker pull patrickstigler/youtube-transcript-to-article
docker run -p 5000:5000 -e OPENAI_API_KEY=sk-... patrickstigler/youtube-transcript-to-article

# GHCR (after logging in: echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin)
docker pull ghcr.io/patrickstigler/youtube-transcript-to-article:latest
docker run -p 5000:5000 -e OPENAI_API_KEY=sk-... ghcr.io/patrickstigler/youtube-transcript-to-article:latest
```

### CI: build and push

Workflow: [`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml).

**GHCR** uses the default `GITHUB_TOKEN` (workflow permission `packages: write` is already set in the workflow).

**Docker Hub** — add these [repository secrets](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions#creating-secrets-for-a-repository):

| Secret | Required | Description |
|--------|----------|-------------|
| `DOCKERHUB_TOKEN` | Yes, for Docker Hub | [Access token](https://hub.docker.com/settings/security) or account password |
| `DOCKERHUB_USERNAME` | No | Defaults to your GitHub `repository_owner` if omitted |

Tags pushed:

- `sha-<short-git-sha>` on every qualifying run
- `latest` when the push is to the repository default branch
- `v*` when you push a matching Git tag (e.g. `v1.0.0`)

With Docker Compose, set `OPENAI_API_KEY` in your environment or `.env` file (see `docker-compose.yml`).

### LocalAI example

Run LocalAI on the host and point the container at it:

```yaml
environment:
  - OPENAI_API_KEY=not-needed
  - DEFAULT_MODEL_HOST=localai
  - LOCALAI_BASE_URL=http://host.docker.internal:8080/v1
```

## API

### `POST /api/generate`

JSON body:

```json
{
  "video_id": "https://www.youtube.com/watch?v=VIDEO_ID or VIDEO_ID",
  "detail_level": "standard",
  "word_limit": 300,
  "target_lang": "de",
  "model": "gpt-4o-mini",
  "model_host": "openai"
}
```

- **`video_id`** (required): URL or 11-character ID.
- **`detail_level`**: `brief` | `standard` | `detailed` | `comprehensive`. Legacy: `summary` → brief, `detailed` unchanged.
- **`word_limit`** (optional): Positive integer; response should be about that many words.
- **`target_lang`** (optional): ISO language code for the written output.
- **`model`** (optional): Defaults to `DEFAULT_MODEL`.
- **`model_host`**: `openai` | `localai` — defaults to `DEFAULT_MODEL_HOST`.

Success response includes `article`, `video_id`, `video_title`, `video_description` (watch-page text, best-effort), `detail_level`, `model`, and `model_host`. Errors return JSON `{ "error": "..." }` with appropriate HTTP status (400, 404, 422, 429, 502, 503).

### `POST /api/transcript`

Returns raw transcript text for a video (same `video_id` / `target_lang` as before), plus `video_title` and `video_description`.

### `GET /api/config`

Public defaults for the web UI (model name, host, allowed detail levels). No secrets.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
python app.py
```

MCP (no API key): `python mcp_server.py`

Open `http://127.0.0.1:5000` for the web UI.

The app is also available on unRAID Community Apps as `youtube-transcript-to-article`.

## License

This project uses the [MIT License](LICENSE).

## Contributing

Contributions are welcome. Please open an issue or pull request.

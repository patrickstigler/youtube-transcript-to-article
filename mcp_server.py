"""
Model Context Protocol (MCP) server: YouTube transcript + video description/metadata only.

No OpenAI or other LLM keys are required — the assistant that connects to this MCP
generates articles or summaries from the returned text.

Transports:
  - stdio (default): Cursor / Claude Desktop — use `docker run -i` for stdio in Docker.
  - streamable-http: set MCP_TRANSPORT=streamable-http (default in Docker when APP_MODE=mcp).

Environment: same HTTP/timeouts as the web app (HTTP_REQUEST_TIMEOUT, etc.). No OPENAI_API_KEY.
"""

from __future__ import annotations

import json
import logging
import os

from mcp.server.fastmcp import FastMCP

from app import extract_video_id, get_transcript, get_video_info_scrape, is_valid_youtube_video_id
from youtube_transcript_api import (
    NoTranscriptFound,
    TooManyRequests,
    TranscriptsDisabled,
    VideoUnavailable,
    InvalidVideoId,
)

logger = logging.getLogger(__name__)


def _mcp_host() -> str:
    if os.getenv("MCP_TRANSPORT") == "streamable-http":
        return os.getenv("FASTMCP_HOST", os.getenv("MCP_HTTP_HOST", "0.0.0.0"))
    return os.getenv("FASTMCP_HOST", os.getenv("MCP_HTTP_HOST", "127.0.0.1"))


def _mcp_port() -> int:
    return int(os.getenv("FASTMCP_PORT", os.getenv("MCP_HTTP_PORT", "8000")))


mcp = FastMCP(
    "YouTube Transcript & Description",
    instructions=(
        "Returns YouTube video data for use by the host AI: (1) caption transcript text, "
        "(2) title / channel / description from the watch page. "
        "Does not call OpenAI or any LLM — you write the article or summary yourself from this content."
    ),
    json_response=True,
    host=_mcp_host(),
    port=_mcp_port(),
)


def _metadata_payload(info: dict, video_id: str) -> dict:
    return {
        "video_id": video_id,
        "video_title": info.get("title", ""),
        "video_description": info.get("description", ""),
        "channel": info.get("channel", ""),
    }


@mcp.tool()
def get_youtube_transcript(video_id: str, target_lang: str | None = None) -> str:
    """Fetch caption transcript text for a video (plus title, channel, and description from the watch page).

    Args:
        video_id: Full watch URL or 11-character video ID.
        target_lang: Optional ISO language code to prefer for captions (e.g. en, de).
    """
    video_input = (video_id or "").strip()
    if not video_input:
        return json.dumps({"error": "video_id is required"})

    tlang = (target_lang or "").strip() or None
    vid = extract_video_id(video_input)
    if not is_valid_youtube_video_id(vid):
        return json.dumps({"error": "Could not parse a valid 11-character YouTube video ID"})

    try:
        text = get_transcript(vid, tlang)
        info = get_video_info_scrape(vid)
    except InvalidVideoId:
        return json.dumps({"error": "Invalid or malformed video ID"})
    except VideoUnavailable:
        return json.dumps({"error": "Video is unavailable, private, or removed"})
    except TranscriptsDisabled:
        return json.dumps({"error": "Transcripts/captions are disabled for this video"})
    except NoTranscriptFound:
        return json.dumps({"error": "No transcript could be found for this video"})
    except TooManyRequests:
        return json.dumps({"error": "YouTube rate limit reached; try again shortly"})
    except Exception as e:
        logger.exception("get_youtube_transcript failed")
        return json.dumps({"error": str(e)})

    out = _metadata_payload(info, vid)
    out["transcript"] = text
    return json.dumps(out)


@mcp.tool()
def get_youtube_video_description(video_id: str) -> str:
    """Fetch title, channel, and description text from the video watch page (no captions API).

    Use when you only need the uploader description, or when transcripts are unavailable.
    """
    video_input = (video_id or "").strip()
    if not video_input:
        return json.dumps({"error": "video_id is required"})

    vid = extract_video_id(video_input)
    if not is_valid_youtube_video_id(vid):
        return json.dumps({"error": "Could not parse a valid 11-character YouTube video ID"})

    try:
        info = get_video_info_scrape(vid)
    except Exception as e:
        logger.exception("get_youtube_video_description failed")
        return json.dumps({"error": str(e)})

    if info.get("title") == "Unknown title" and not info.get("description"):
        return json.dumps({"error": "Could not load video page; video may be unavailable or private"})

    return json.dumps(_metadata_payload(info, vid))


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)  # type: ignore[arg-type]

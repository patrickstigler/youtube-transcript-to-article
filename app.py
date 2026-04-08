import os
import re
import json
import logging
import html as html_module
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify, render_template
from openai import OpenAI, APIError, APITimeoutError
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    InvalidVideoId,
    TooManyRequests,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

REQUEST_TIMEOUT = float(os.getenv("HTTP_REQUEST_TIMEOUT", "30"))
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "180"))
MAX_TRANSCRIPT_CHARS = int(os.getenv("MAX_TRANSCRIPT_CHARS", "120000"))

DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
DEFAULT_MODEL_HOST = os.getenv("DEFAULT_MODEL_HOST", "openai").lower()

LOCALAI_BASE_URL = os.getenv("LOCALAI_BASE_URL", "http://localhost:8080/v1").rstrip("/")
if not LOCALAI_BASE_URL.endswith("/v1"):
    LOCALAI_BASE_URL = f"{LOCALAI_BASE_URL.rstrip('/')}/v1"

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL")
if OPENAI_BASE_URL:
    OPENAI_BASE_URL = OPENAI_BASE_URL.rstrip("/")
    if not OPENAI_BASE_URL.endswith("/v1"):
        OPENAI_BASE_URL = f"{OPENAI_BASE_URL.rstrip('/')}/v1"

DETAIL_INSTRUCTIONS = {
    "brief": (
        "Produce a concise summary: capture the main thesis and 3–6 key takeaways. "
        "Use short paragraphs or tight bullets. Aim for clarity over length."
    ),
    "standard": (
        "Produce a balanced article: introduction, clearly separated sections for main themes, "
        "and a short conclusion. Suitable for a general blog post."
    ),
    "detailed": (
        "Produce a detailed professional article: structured headings, nuanced explanation of arguments, "
        "examples from the transcript where helpful, and a substantive conclusion."
    ),
    "comprehensive": (
        "Produce a comprehensive deep dive: exhaustive coverage of themes, subtopics, caveats, "
        "and implications; use clear hierarchy (headings and subheadings); integrate evidence from the transcript."
    ),
}

# Legacy API values
_LEGACY_DETAIL = {"summary": "brief", "detailed": "detailed"}


def _normalize_detail_level(raw: str | None) -> str:
    if not raw:
        return "standard"
    key = raw.strip().lower()
    return _LEGACY_DETAIL.get(key, key)


def get_openai_client(model_host: str) -> OpenAI:
    """Build an OpenAI-compatible client for the chosen host."""
    host = (model_host or DEFAULT_MODEL_HOST).lower()
    if host == "localai":
        api_key = os.getenv("LOCALAI_API_KEY") or os.getenv("OPENAI_API_KEY") or "localai"
        return OpenAI(api_key=api_key, base_url=LOCALAI_BASE_URL, timeout=OPENAI_TIMEOUT)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    kwargs = {"api_key": api_key, "timeout": OPENAI_TIMEOUT}
    if OPENAI_BASE_URL:
        kwargs["base_url"] = OPENAI_BASE_URL
    return OpenAI(**kwargs)


def extract_video_id(url_or_id: str) -> str:
    """Extract the video ID from a YouTube URL or return the input if it is already an ID."""
    video_id_match = re.match(
        r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
        url_or_id.strip(),
    )
    return video_id_match.group(1) if video_id_match else url_or_id.strip()


def is_valid_youtube_video_id(video_id: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_-]{11}$", video_id))


def _description_from_watch_html(page_html: str, soup: BeautifulSoup) -> str:
    """Best-effort video description from watch page HTML."""
    for prop in ("og:description",):
        meta = soup.find("meta", property=prop)
        if meta and meta.get("content"):
            text = html_module.unescape(meta["content"]).strip()
            if text:
                return text
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        text = html_module.unescape(meta["content"]).strip()
        if text:
            return text
    # Embedded player response JSON (escaped string)
    m = re.search(r'"shortDescription"\s*:\s*"((?:[^"\\]|\\.)*)"', page_html)
    if m:
        raw = m.group(1)
        try:
            return json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            return raw.replace("\\n", "\n").replace('\\"', '"').replace("\\\\", "\\")
    return ""


def get_video_info_scrape(video_id: str) -> dict:
    """Fetch title, channel, and description from the watch page (best-effort)."""
    empty = {"title": "Unknown title", "channel": "Unknown channel", "description": ""}
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "youtube-transcript-to-article/1.0"})
        if response.status_code != 200:
            return empty

        page_html = response.text
        soup = BeautifulSoup(page_html, "html.parser")
        title = "Unknown title"
        meta = soup.find("meta", property="og:title")
        if meta and meta.get("content"):
            title = html_module.unescape(meta["content"]).strip() or title

        channel = "Unknown channel"
        channel_tag = soup.find("a", {"class": "yt-simple-endpoint style-scope yt-formatted-string"})
        if channel_tag and channel_tag.text:
            channel = channel_tag.text.strip()

        description = _description_from_watch_html(page_html, soup)

        return {"title": title, "channel": channel, "description": description}
    except Exception as e:
        logger.warning("Error scraping video info: %s", e)
        return dict(empty)


def get_transcript(video_id: str, target_lang: str | None = None) -> str:
    """Fetch transcript text for the video."""
    try:
        if target_lang:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[target_lang])
        else:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
    except NoTranscriptFound:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        available = [t.language_code for t in transcript_list]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=available)

    text = " ".join(t["text"] for t in transcript)
    if len(text) > MAX_TRANSCRIPT_CHARS:
        text = text[:MAX_TRANSCRIPT_CHARS] + "\n\n[Transcript truncated for length.]"
    return text


def build_system_prompt(detail_level: str, word_limit: int | None) -> str:
    """System instructions for the assistant."""
    instr = DETAIL_INSTRUCTIONS.get(detail_level, DETAIL_INSTRUCTIONS["standard"])
    parts = [
        "You turn YouTube transcript text into polished Markdown for readers.",
        "Stay faithful to the transcript; do not invent facts or citations not present in the input.",
        f"Depth / style: {instr}",
    ]
    if word_limit is not None and word_limit > 0:
        parts.append(
            f"The user's primary requirement is length: the entire Markdown response must be "
            f"approximately {word_limit} words (stay within roughly ±10% of that target)."
        )
    parts.append("Use Markdown headings where appropriate. Do not prepend a disclaimer about being an AI.")
    return "\n\n".join(parts)


def call_llm(
    client: OpenAI,
    model: str,
    transcript: str,
    detail_level: str,
    target_lang: str | None,
    word_limit: int | None,
) -> str:
    system = build_system_prompt(detail_level, word_limit)
    user_parts = [
        "Transform the following INPUT transcript into the requested output.",
        "",
        "---",
        transcript,
        "---",
    ]
    if target_lang:
        user_parts.append(f"Write the full response in language: {target_lang}.")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "\n".join(user_parts)},
            ],
        )
        content = response.choices[0].message.content
        return (content or "").strip()
    except APITimeoutError as e:
        logger.error("OpenAI timeout: %s", e)
        raise RuntimeError("The model request timed out. Try again or shorten the video.") from e
    except APIError as e:
        logger.error("OpenAI API error: %s", e)
        raise RuntimeError(f"Model API error: {e}") from e


def generate_article(
    client: OpenAI,
    model: str,
    transcript: str,
    detail_level: str = "standard",
    target_lang: str | None = None,
    word_limit: int | None = None,
) -> str:
    """Generate article text from transcript."""
    return call_llm(client, model, transcript, detail_level, target_lang, word_limit)


def _parse_json_body():
    if not request.is_json:
        return None, (jsonify({"error": "Expected application/json"}), 400)
    data = request.get_json(silent=True)
    if data is None:
        return None, (jsonify({"error": "Invalid JSON body"}), 400)
    return data, None


def _coerce_word_limit(raw) -> tuple[int | None, str | None]:
    if raw is None or raw == "":
        return None, None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None, "word_limit must be a positive integer"
    if n < 1:
        return None, "word_limit must be at least 1"
    if n > 50000:
        return None, "word_limit is too large (max 50000)"
    return n, None


@app.route("/api/generate", methods=["POST"])
def generate():
    """Generate an article from a YouTube video transcript."""
    data, err = _parse_json_body()
    if err:
        return err

    video_input = (data.get("video_id") or "").strip()
    if not video_input:
        return jsonify({"error": "video_id is required"}), 400

    detail_level = _normalize_detail_level(data.get("detail_level"))
    if detail_level not in DETAIL_INSTRUCTIONS:
        allowed = ", ".join(sorted(DETAIL_INSTRUCTIONS))
        return jsonify({"error": f"detail_level must be one of: {allowed}"}), 400

    word_limit, wl_err = _coerce_word_limit(data.get("word_limit"))
    if wl_err:
        return jsonify({"error": wl_err}), 400

    target_lang = (data.get("target_lang") or "").strip() or None
    model = (data.get("model") or "").strip() or DEFAULT_MODEL
    model_host = (data.get("model_host") or "").strip().lower() or DEFAULT_MODEL_HOST
    if model_host not in ("openai", "localai"):
        return jsonify({"error": 'model_host must be "openai" or "localai"'}), 400

    video_id = extract_video_id(video_input)
    if not is_valid_youtube_video_id(video_id):
        return jsonify({"error": "Could not parse a valid 11-character YouTube video ID"}), 400

    try:
        client = get_openai_client(model_host)
    except ValueError as e:
        return jsonify({"error": str(e)}), 503

    try:
        transcript = get_transcript(video_id, target_lang)
        article = generate_article(client, model, transcript, detail_level, target_lang, word_limit)
        video_info = get_video_info_scrape(video_id)
    except InvalidVideoId:
        return jsonify({"error": "Invalid or malformed video ID"}), 400
    except VideoUnavailable:
        return jsonify({"error": "Video is unavailable, private, or removed"}), 404
    except TranscriptsDisabled:
        return jsonify({"error": "Transcripts/captions are disabled for this video"}), 422
    except NoTranscriptFound:
        return jsonify({"error": "No transcript could be found for this video"}), 422
    except TooManyRequests:
        return jsonify({"error": "YouTube rate limit reached; try again shortly"}), 429
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    except Exception as e:
        logger.exception("Generate failed")
        return jsonify({"error": str(e)}), 502

    return jsonify(
        {
            "article": article,
            "video_id": video_id,
            "video_title": video_info["title"],
            "video_description": video_info.get("description", ""),
            "detail_level": detail_level,
            "model": model,
            "model_host": model_host,
        }
    )


@app.route("/api/transcript", methods=["POST"])
def transcript():
    """Return the plain transcript for a video."""
    data, err = _parse_json_body()
    if err:
        return err

    video_input = (data.get("video_id") or "").strip()
    if not video_input:
        return jsonify({"error": "video_id is required"}), 400

    target_lang = (data.get("target_lang") or "").strip() or None

    video_id = extract_video_id(video_input)
    if not is_valid_youtube_video_id(video_id):
        return jsonify({"error": "Could not parse a valid 11-character YouTube video ID"}), 400

    try:
        text = get_transcript(video_id, target_lang)
        video_info = get_video_info_scrape(video_id)
    except InvalidVideoId:
        return jsonify({"error": "Invalid or malformed video ID"}), 400
    except VideoUnavailable:
        return jsonify({"error": "Video is unavailable, private, or removed"}), 404
    except TranscriptsDisabled:
        return jsonify({"error": "Transcripts/captions are disabled for this video"}), 422
    except NoTranscriptFound:
        return jsonify({"error": "No transcript could be found for this video"}), 422
    except TooManyRequests:
        return jsonify({"error": "YouTube rate limit reached; try again shortly"}), 429
    except Exception as e:
        logger.exception("Transcript fetch failed")
        return jsonify({"error": str(e)}), 502

    return jsonify(
        {
            "transcript": text,
            "video_id": video_id,
            "video_title": video_info["title"],
            "video_description": video_info.get("description", ""),
        }
    )


@app.route("/api/config", methods=["GET"])
def config():
    """Defaults for the web UI (no secrets)."""
    return jsonify(
        {
            "default_model": DEFAULT_MODEL,
            "default_model_host": DEFAULT_MODEL_HOST,
            "detail_levels": list(DETAIL_INSTRUCTIONS.keys()),
        }
    )


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

"""MCP server exposing the transcript tools to AI CLIs.

Compatible with opencode, Claude Code, Freebuff, Cursor, etc.
Run with: yt-transcript-mcp (or python -m yt_transcript.mcp_server)
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .fetch import (
    DEFAULT_LANGUAGES,
    TranscriptError,
    get_transcript,
    get_video_details,
    get_video_info,
    list_available_transcripts,
)

mcp = FastMCP(
    "yt-transcript",
    instructions=(
        "Tools for reading the transcript (captions) of YouTube videos. "
        "Accepts a full URL, youtu.be, shorts or the 11-character ID. "
        "Use get_transcript_tool to get the video text and summarize/analyze it; "
        "use list_transcripts_tool to see which languages are available and "
        "get_video_info_tool for title/channel/duration. Use get_video_details_tool "
        "for the full description and audience comments."
    ),
)

_LANGS_DOC = ", ".join(DEFAULT_LANGUAGES)


@mcp.tool()
def get_transcript_tool(url: str, languages: str | None = None) -> str:
    """Returns the full transcript of a YouTube video.

    Args:
        url: Video URL (youtube.com/watch?v=..., youtu.be/..., shorts/...) or ID.
        languages: Preferred language codes, comma-separated
            (e.g. "en,es,pt"). Defaults to the server default.

    Returns:
        Transcript text with a metadata header, or an error message.
    """
    langs = [l.strip() for l in languages.split(",") if l.strip()] if languages else DEFAULT_LANGUAGES
    try:
        result = get_transcript(url, langs)
    except TranscriptError as e:
        return f"ERROR: {e}"
    return result.as_text()


@mcp.tool()
def list_transcripts_tool(url: str) -> str:
    """Lists the captions/transcripts available for a video (languages and type)."""
    try:
        items = list_available_transcripts(url)
    except TranscriptError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR: {e}"
    if not items:
        return "No captions available for this video."
    lines = [
        f"- {it['language']} ({it['language_code']})"
        f"{' [auto-generated]' if it['is_generated'] else ''}"
        for it in items
    ]
    return "Available captions:\n" + "\n".join(lines)


@mcp.tool()
def get_video_info_tool(url: str) -> str:
    """Returns video metadata: title, channel, duration and upload date."""
    try:
        info = get_video_info(url)
    except TranscriptError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR: {e}"
    return json.dumps(info, ensure_ascii=False, indent=2)


@mcp.tool()
def get_video_details_tool(url: str, max_comments: int = 50) -> str:
    """Returns title, channel, duration, FULL description and comments of a video.

    Useful for understanding context, mentioned links and audience reception.

    Args:
        url: Video URL or ID.
        max_comments: maximum number of comments (default 50).

    Returns:
        JSON with description and a comments list (author, text, likes).
    """
    try:
        details = get_video_details(url, max_comments=max_comments)
    except TranscriptError as e:
        return f"ERROR: {e}"
    except Exception as e:
        return f"ERROR: {e}"
    return json.dumps(details, ensure_ascii=False, indent=2)


def main() -> None:
    """Entry point for the MCP server (stdio)."""
    mcp.run()


if __name__ == "__main__":
    main()

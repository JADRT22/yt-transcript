"""Fetch transcripts of YouTube videos.

The primary path uses `youtube-transcript-api` (no API key required). If it
fails (blocked video, changed API, etc.), it falls back to `yt-dlp`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# URL patterns that carry a video (watch, shorts, embed, live)
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_URL_PATTERNS = (
    re.compile(r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/)|youtu\.be/)([A-Za-z0-9_-]{11})"),
)

# Default language preference for transcripts (tried in order).
DEFAULT_LANGUAGES = ["en", "es", "pt"]


@dataclass
class TranscriptResult:
    """Transcript of a video, ready for consumption by a model."""

    video_id: str
    language: str
    language_code: str
    is_generated: bool
    text: str
    source: str  # "youtube-transcript-api" or "yt-dlp (...)"

    def as_text(self) -> str:
        header = (
            f"Transcript for https://youtu.be/{self.video_id}\n"
            f"Language: {self.language} ({self.language_code})"
            f"{' [auto-generated]' if self.is_generated else ''}\n\n"
        )
        return header + self.text


class TranscriptError(Exception):
    """Friendly error while fetching a transcript."""


def extract_video_id(source: str) -> str:
    """Accepts a full URL, a short URL (youtu.be) or a bare 11-char video ID."""
    source = source.strip()
    if _VIDEO_ID_RE.match(source):
        return source

    for pattern in _URL_PATTERNS:
        match = pattern.search(source)
        if match:
            return match.group(1)

    # watch?v=... may arrive without a matching domain above (proxies, odd params)
    try:
        parsed = urlparse(source)
        query_v = parse_qs(parsed.query).get("v", [None])[0]  # type: ignore[list-item]
        if query_v and _VIDEO_ID_RE.match(query_v):
            return query_v
    except ValueError:
        pass

    raise TranscriptError(
        f"Could not extract the video ID from: {source!r}. "
        "Use a YouTube URL (youtube.com/watch?v=..., youtu.be/..., shorts/...) or the 11-character ID."
    )


def _join_segments(segments) -> str:
    """Join caption segments into a single running text."""
    parts: list[str] = []
    for seg in segments:
        text = seg.text.replace("\n", " ").strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def _fetch_via_api(video_id: str, languages: list[str]) -> TranscriptResult:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    fetched = api.fetch(video_id, languages=languages)
    snippets = list(fetched)
    if not snippets:
        raise TranscriptError("The transcript came back empty.")

    return TranscriptResult(
        video_id=video_id,
        language=fetched.language,
        language_code=fetched.language_code,
        is_generated=fetched.is_generated,
        text=_join_segments(snippets),
        source="youtube-transcript-api",
    )


# Browser to pull cookies from as a last resort against IP blocks.
# Set YT_TRANSCRIPT_COOKIES_BROWSER=none to disable (or chrome, chromium, brave...).
_COOKIES_BROWSER = os.environ.get("YT_TRANSCRIPT_COOKIES_BROWSER", "firefox")

# On-disk cache (~/.cache/yt-transcript): avoids hitting YouTube again when the
# same video is requested twice — important because of rate limits.
# Set YT_TRANSCRIPT_CACHE=none to disable.
_CACHE_DIR = os.environ.get("YT_TRANSCRIPT_CACHE", "")
_CACHE_DISABLED = _CACHE_DIR.lower() == "none"
_CACHE_DIR_PATH = Path(_CACHE_DIR) if _CACHE_DIR else Path.home() / ".cache" / "yt-transcript"


def _cache_get(key: str):
    if _CACHE_DISABLED:
        return None
    try:
        return json.loads((_CACHE_DIR_PATH / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _cache_set(key: str, value) -> None:
    if _CACHE_DISABLED:
        return
    try:
        _CACHE_DIR_PATH.mkdir(parents=True, exist_ok=True)
        (_CACHE_DIR_PATH / f"{key}.json").write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # cache is best-effort; it must never break a fetch


def _cache_key(*parts) -> str:
    raw = "||".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def _ytdlp_run(
    extra_args: list[str], timeout: int, allow_cookies: bool = False
) -> subprocess.CompletedProcess:
    """Run yt-dlp through a cascade of YouTube anti-block workarounds:

    1. default client (web)
    2. android client (bypasses the "confirm you're not a bot" check)
    3. browser cookies + --ignore-no-formats-error (cures IP blocks/429s;
       --ignore-no-formats-error avoids the empty-format error of logged sessions)
    """
    base = [sys.executable, "-m", "yt_dlp", "--skip-download", "--no-warnings"]
    attempts: list[list[str]] = [
        [],
        ["--extractor-args", "youtube:player_client=android"],
    ]
    used_cookies = False
    if allow_cookies and _COOKIES_BROWSER.lower() != "none":
        attempts.append(
            [
                "--cookies-from-browser", _COOKIES_BROWSER,
                "--ignore-no-formats-error",
                "--extractor-args", "youtube:player_client=android",
            ]
        )
        used_cookies = True

    last_err = ""
    for attempt_args in attempts:
        proc = subprocess.run(
            base + attempt_args + extra_args, capture_output=True, text=True, timeout=timeout
        )
        if proc.returncode == 0:
            return proc
        lines = (proc.stderr or "").strip().splitlines()
        last_err = lines[-1] if lines else ""
    suffix = " (incl. cookies)" if used_cookies else ""
    raise TranscriptError(
        f"yt-dlp failed on all attempts{suffix}. Detail: {last_err or 'no output'}"
    )


def _client_combos() -> list[tuple[str, list[str]]]:
    """(name, extra args) player client/cookie combinations, in order."""
    combos = [
        ("web", []),
        ("android", ["--extractor-args", "youtube:player_client=android"]),
    ]
    if _COOKIES_BROWSER.lower() != "none":
        combos += [
            ("web+cookies", ["--cookies-from-browser", _COOKIES_BROWSER, "--ignore-no-formats-error"]),
            (
                "android+cookies",
                [
                    "--extractor-args", "youtube:player_client=android",
                    "--cookies-from-browser", _COOKIES_BROWSER,
                    "--ignore-no-formats-error",
                ],
            ),
        ]
    return combos


def _fetch_via_ytdlp(video_id: str, languages: list[str]) -> TranscriptResult:
    """Fallback: download auto/manual captions via yt-dlp and convert to plain text.

    Tries several player client + cookie combinations; success only counts if
    the .vtt file is actually written (each combo fails differently).
    """
    import tempfile

    lang_codes = ",".join(languages)
    url = f"https://www.youtube.com/watch?v={video_id}"
    errors: list[str] = []
    clean_no_subs = False

    with tempfile.TemporaryDirectory(prefix="yt-transcript-") as tmp:
        for name, combo_args in _client_combos():
            cmd = [
                sys.executable, "-m", "yt_dlp", "--no-warnings",
                # --no-simulate is mandatory: without it yt-dlp runs in simulation
                # mode and does NOT write caption files.
                "--no-simulate", "--skip-download",
                "--write-auto-subs", "--write-subs",
                "--sub-langs", lang_codes,
                "--sub-format", "vtt/srv3/best",
                "-P", tmp,
                *combo_args,
                url,
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            except subprocess.TimeoutExpired:
                errors.append(f"{name}: timeout")
                continue

            candidates = sorted(
                Path(tmp).glob(f"*{video_id}*.vtt"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if candidates:
                text = _vtt_to_text(candidates[0].read_text(encoding="utf-8"))
                if text:
                    return TranscriptResult(
                        video_id=video_id,
                        language="Unknown (via yt-dlp)",
                        language_code=languages[0] if languages else "en",
                        is_generated=True,
                        text=text,
                        source=f"yt-dlp ({name})",
                    )

            lines = (proc.stderr or "").strip().splitlines()
            detail = lines[-1] if lines else "no output"
            if proc.returncode == 0:
                clean_no_subs = True
                errors.append(f"{name}: ok, but no captions in languages {lang_codes}")
            else:
                errors.append(f"{name}: {detail}")

    if clean_no_subs:
        raise TranscriptError(
            f"This video has no captions in the attempted languages ({lang_codes}). "
            "Try other languages with -l/--languages."
        )
    raise TranscriptError(
        "yt-dlp could not download captions. Attempts:\n- " + "\n- ".join(errors)
    )


def _vtt_to_text(vtt: str) -> str:
    """Convert WebVTT to running text, stripping headers, timings and tags."""
    lines_out: list[str] = []
    seen: set[str] = set()
    for raw_line in vtt.splitlines():
        line = raw_line.strip()
        if (
            not line
            or line == "WEBVTT"
            or line.startswith(("Kind:", "Language:", "NOTE", "STYLE"))
            or "-->" in line
            or line.isdigit()
        ):
            continue
        line = re.sub(r"<[^>]+>", "", line)  # <c>, <00:00:00.000> etc. tags
        if line in seen:  # scrolling captions repeat the previous line
            continue
        seen.add(line)
        lines_out.append(line)
    return " ".join(lines_out)


def get_transcript(source: str, languages: list[str] | None = None) -> TranscriptResult:
    """Fetch the transcript of a video from a URL or ID (cached on disk).

    Tries the captions API first; on failure, falls back to yt-dlp.
    """
    languages = languages or DEFAULT_LANGUAGES
    video_id = extract_video_id(source)

    cache_key = _cache_key("transcript", video_id, ",".join(languages))
    cached = _cache_get(cache_key)
    if cached:
        return TranscriptResult(**cached)

    try:
        result = _fetch_via_api(video_id, languages)
    except Exception as api_err:
        try:
            result = _fetch_via_ytdlp(video_id, languages)
        except Exception as ytdlp_err:
            raise TranscriptError(
                f"Could not retrieve the transcript for {video_id}.\n"
                f"- youtube-transcript-api: {api_err}\n"
                f"- yt-dlp: {ytdlp_err}"
            ) from ytdlp_err

    _cache_set(cache_key, asdict(result))
    return result


def get_video_info(source: str) -> dict:
    """Lightweight video metadata (title, channel, duration) via yt-dlp (cached)."""
    video_id = extract_video_id(source)

    cache_key = _cache_key("info", video_id)
    cached = _cache_get(cache_key)
    if cached:
        return cached

    url = f"https://www.youtube.com/watch?v={video_id}"
    proc = _ytdlp_run(
        [
            "--no-playlist",
            "--print", "%(title)s|||%(channel)s|||%(duration_string)s|||%(upload_date)s",
            url,
        ],
        timeout=90,
        allow_cookies=True,
    )
    title, channel, duration, upload_date = (proc.stdout.strip().split("|||") + ["", "", "", ""])[:4]
    if not title:
        raise TranscriptError(f"yt-dlp returned no metadata for {video_id}.")
    info = {
        "video_id": video_id,
        "url": url,
        "title": title,
        "channel": channel,
        "duration": duration,
        "upload_date": upload_date,
    }
    _cache_set(cache_key, info)
    return info


def list_available_transcripts(source: str) -> list[dict]:
    """List the captions/transcripts available for a video.

    Tries the captions API first; if YouTube blocks it, falls back to yt-dlp.
    """
    video_id = extract_video_id(source)
    cache_key = _cache_key("list", video_id)
    cached = _cache_get(cache_key)
    if cached:
        return cached
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        transcript_list = YouTubeTranscriptApi().list(video_id)
        items = [
            {
                "language": t.language,
                "language_code": t.language_code,
                "is_generated": t.is_generated,
            }
            for t in transcript_list
        ]
        _cache_set(cache_key, items)
        return items
    except Exception:
        pass  # fall through to yt-dlp below

    url = f"https://www.youtube.com/watch?v={video_id}"
    proc = _ytdlp_run(["--list-subs", "--no-playlist", url], timeout=90, allow_cookies=True)
    items: list[dict] = []
    seen: set[tuple[str, bool]] = set()
    section_auto = False
    for raw in proc.stdout.splitlines():
        if "[info] Available automatic captions" in raw:
            section_auto = True
            continue
        if "[info] Available subtitles" in raw:
            section_auto = False
            continue
        line = raw.strip()
        if not line or line.startswith("["):
            continue
        parts = re.split(r"\s{2,}", line)
        if len(parts) >= 3 and re.match(r"^[A-Za-z0-9-]{2,12}$", parts[0]):
            key = (parts[0], section_auto)
            if key not in seen:
                seen.add(key)
                items.append(
                    {
                        "language": parts[1],
                        "language_code": parts[0],
                        "is_generated": section_auto,
                    }
                )
    _cache_set(cache_key, items)
    return items


def get_video_details(
    source: str, max_comments: int = 50, comment_sort: str = "top"
) -> dict:
    """Video description and comments, plus the basic metadata.

    Uses yt-dlp --dump-json with --write-comments, trying the same client
    cascade. Not every client delivers comments: if a combo succeeds without
    any, move on to the next one.
    """
    video_id = extract_video_id(source)
    cache_key = _cache_key("details", video_id, max_comments, comment_sort)
    cached = _cache_get(cache_key)
    if cached:
        return cached

    url = f"https://www.youtube.com/watch?v={video_id}"
    extractor = f"youtube:max_comments={max_comments},all;comment_sort={comment_sort}"
    errors: list[str] = []
    info_no_comments: dict | None = None

    for name, combo_args in _client_combos():
        cmd = [
            sys.executable, "-m", "yt_dlp", "--no-warnings",
            "--skip-download", "--no-playlist",
            "--write-comments",
            "--dump-json",
            "--extractor-args", extractor,
            *combo_args,
            url,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            errors.append(f"{name}: timeout")
            continue

        json_line = ""
        for line in reversed((proc.stdout or "").strip().splitlines()):
            if line.startswith("{"):
                json_line = line
                break
        info = None
        if json_line:
            try:
                info = json.loads(json_line)
            except json.JSONDecodeError:
                info = None

        if isinstance(info, dict):
            comments = [
                {
                    "author": c.get("author", ""),
                    "text": c.get("text", ""),
                    "likes": c.get("like_count"),
                    "is_reply": bool(c.get("parent")),
                }
                for c in (info.get("comments") or [])
            ]
            if not comments and max_comments > 0:
                # Client connected but delivers no comments (e.g. android).
                info_no_comments = info
                errors.append(f"{name}: ok, but 0 comments")
                continue
            details = {
                "video_id": video_id,
                "url": url,
                "title": info.get("title", ""),
                "channel": info.get("channel", ""),
                "duration": info.get("duration_string", ""),
                "description": (info.get("description") or "").strip(),
                "comment_count": info.get("comment_count"),
                "comments": comments,
                "source": f"yt-dlp ({name})",
            }
            _cache_set(cache_key, details)
            return details

        lines = (proc.stderr or "").strip().splitlines()
        errors.append(f"{name}: {lines[-1] if lines else 'no output'}")

    if info_no_comments is not None:
        # Comments are probably disabled for this video; return the rest.
        details = {
            "video_id": video_id,
            "url": url,
            "title": info_no_comments.get("title", ""),
            "channel": info_no_comments.get("channel", ""),
            "duration": info_no_comments.get("duration_string", ""),
            "description": (info_no_comments.get("description") or "").strip(),
            "comment_count": info_no_comments.get("comment_count"),
            "comments": [],
            "source": "yt-dlp (no comments)",
        }
        _cache_set(cache_key, details)
        return details
    raise TranscriptError(
        "Could not fetch description/comments. Attempts:\n- " + "\n- ".join(errors)
    )


def result_to_json(result: TranscriptResult) -> str:
    return json.dumps(
        {
            "video_id": result.video_id,
            "language": result.language,
            "language_code": result.language_code,
            "is_generated": result.is_generated,
            "source": result.source,
            "text": result.text,
        },
        ensure_ascii=False,
    )

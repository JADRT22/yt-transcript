"""yt-transcript CLI: prints the transcript to stdout for the agent to read."""

from __future__ import annotations

import argparse
import json
import sys

from .fetch import (
    DEFAULT_LANGUAGES,
    TranscriptError,
    get_transcript,
    get_video_details,
    get_video_info,
    list_available_transcripts,
    result_to_json,
)
from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yt-transcript",
        description="Fetch the transcript (captions) of a YouTube video. "
        "Useful for AI agents to read the video's content.",
    )
    parser.add_argument("url", help="Video URL or 11-character ID")
    parser.add_argument(
        "-l", "--languages",
        default=",".join(DEFAULT_LANGUAGES),
        help=f"Preferred language codes, comma-separated (default: {','.join(DEFAULT_LANGUAGES)})",
    )
    parser.add_argument("--json", action="store_true", help="JSON output (metadata + text)")
    parser.add_argument(
        "--info", action="store_true",
        help="Show only metadata (title, channel, duration) without the transcript",
    )
    parser.add_argument(
        "--desc", action="store_true",
        help="Show description + comments of the video (JSON). Combine with --max-comments",
    )
    parser.add_argument(
        "--max-comments", type=int, default=50, metavar="N",
        help="Maximum number of comments for --desc (default: 50)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List the captions available for the video",
    )
    parser.add_argument(
        "--no-fallback", action="store_true",
        help="Do not use yt-dlp as a fallback if the primary API fails",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    langs = [l.strip() for l in args.languages.split(",") if l.strip()]

    try:
        if args.list:
            items = list_available_transcripts(args.url)
            if not items:
                print("No captions available for this video.")
            else:
                print("Available captions:")
                for it in items:
                    tag = " [auto-generated]" if it["is_generated"] else ""
                    print(f"- {it['language']} ({it['language_code']}){tag}")
            return 0

        if args.desc:
            print(json.dumps(get_video_details(args.url, max_comments=args.max_comments), ensure_ascii=False, indent=2))
            return 0

        if args.info:
            print(json.dumps(get_video_info(args.url), ensure_ascii=False, indent=2))
            return 0

        if args.no_fallback:
            from .fetch import _fetch_via_api, extract_video_id

            result = _fetch_via_api(extract_video_id(args.url), langs)
        else:
            result = get_transcript(args.url, langs)

        if args.json:
            print(result_to_json(result))
        else:
            print(result.as_text())
        return 0

    except TranscriptError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

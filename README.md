# yt-transcript — YouTube Transcript MCP Server

Give your AI agent **eyes for YouTube**. A lightweight youtube transcript mcp server + CLI that fetches the **transcript, description, and comments** of any YouTube video — so your agent can read, summarize, and analyze video content.

## Copy-paste in 30s / Copie e rode em 30s

```bash
git clone https://github.com/JADRT22/yt-transcript.git
cd yt-transcript
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/yt-transcript "https://www.youtube.com/watch?v=VIDEO_ID"
```

> 🇧🇷 **Em Português:** servidor MCP + CLI de transcrição do YouTube (youtube transcript mcp server) — busca transcrição, descrição e comentários de qualquer vídeo para seu agente resumir e analisar, com cache em disco e fallback em 4 camadas contra bloqueio do YouTube.

Works with **opencode, Claude Code, Freebuff, Cursor, and any MCP-compatible client** — or as a plain CLI any agent can call.

## Why this one?

YouTube aggressively blocks scripted access ("confirm you're not a bot", HTTP 429). Most transcript tools break the first time YouTube pushes back. This one ships a **4-layer fallback cascade** baked in:

| Layer | What it does |
|---|---|
| 1. `youtube-transcript-api` | Fast path, no API key needed |
| 2. yt-dlp web client | Baseline fallback |
| 3. yt-dlp android client | Bypasses the "not a bot" check on most videos |
| 4. yt-dlp + browser cookies | Cures hard IP blocks / 429s (uses your Firefox/Chrome cookies) |

Plus:

- **Disk cache** (`~/.cache/yt-transcript/`) — second call for the same video is ~10x faster and consumes zero rate limit
- **Description + comments** — likes, authors, replies; great context for richer summaries
- **Language aware** — pick preferred languages; lists everything available per video
- **Zero config, zero API keys**

## Install

```bash
git clone https://github.com/JADRT22/yt-transcript.git
cd yt-transcript
python3 -m venv .venv
.venv/bin/pip install -e .
```

## MCP setup

Point your client at the server binary:

```
/absolute/path/to/yt-transcript/.venv/bin/yt-transcript-mcp
```

<details>
<summary><b>opencode</b></summary>

In `~/.config/opencode/opencode.json` (global) or `opencode.json` (project):

```json
{
  "mcp": {
    "yt-transcript": {
      "type": "local",
      "command": ["/absolute/path/to/yt-transcript/.venv/bin/yt-transcript-mcp"],
      "enabled": true
    }
  }
}
```
</details>

<details>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add yt-transcript -- /absolute/path/to/yt-transcript/.venv/bin/yt-transcript-mcp
```
</details>

<details>
<summary><b>Freebuff (and other agents with mcp.json)</b></summary>

Create a `mcp.json` in the project root where the agent runs:

```json
{
  "mcpServers": {
    "yt-transcript": {
      "command": "/absolute/path/to/yt-transcript/.venv/bin/yt-transcript-mcp"
    }
  }
}
```
</details>

<details>
<summary><b>No MCP? Use the CLI</b></summary>

Any agent that runs shell commands can read the output directly:

```bash
/absolute/path/to/yt-transcript/.venv/bin/yt-transcript "https://www.youtube.com/watch?v=VIDEO_ID"
```
</details>

## MCP tools

| Tool | Description |
|---|---|
| `get_transcript_tool(url, languages?)` | Full transcript of the video |
| `list_transcripts_tool(url)` | Available captions (languages, auto-generated?) |
| `get_video_info_tool(url)` | Title, channel, duration, upload date |
| `get_video_details_tool(url, max_comments?)` | **Full description + comments** (author, text, likes) |

Example prompts once connected:

```
Summarize this video: https://www.youtube.com/watch?v=...

What are people saying in the comments of this video? [URL]

Compare what the video claims with what the description promises: [URL]
```

## CLI usage

```bash
# Full transcript (default languages: en, es, pt)
.venv/bin/yt-transcript "https://www.youtube.com/watch?v=VIDEO_ID"

# Metadata only
.venv/bin/yt-transcript VIDEO_ID --info

# Description + comments (JSON)
.venv/bin/yt-transcript VIDEO_ID --desc --max-comments 50

# Available captions
.venv/bin/yt-transcript VIDEO_ID --list

# JSON output / other languages
.venv/bin/yt-transcript VIDEO_ID --json
.venv/bin/yt-transcript VIDEO_ID -l de,fr
```

Accepts `youtube.com/watch?v=...`, `youtu.be/...`, `youtube.com/shorts/...`, or the bare 11-character ID.

## Configuration

| Environment variable | Default | Purpose |
|---|---|---|
| `YT_TRANSCRIPT_COOKIES_BROWSER` | `firefox` | Browser for the cookie fallback (`chrome`, `chromium`, `brave`, ...; `none` disables) |
| `YT_TRANSCRIPT_CACHE` | `~/.cache/yt-transcript` | Cache directory (`none` disables) |

To force a fresh fetch for one video, delete its file (SHA-256-named) from the cache directory.

## How it works

1. `extract_video_id` normalizes any YouTube URL format into a video ID.
2. Transcripts: captions API first; on any failure, yt-dlp downloads the `.vtt` through the client cascade and converts it to plain text (each attempt only counts if the caption file is actually written — yt-dlp's simulation mode silently skips it, and `--no-simulate` guards that).
3. Metadata/details: `yt-dlp --print` / `--dump-json --write-comments` through the same cascade.
4. Everything is cached on disk; agents can retry cheaply.

## Limitations

- Videos with **no captions at all** can't be transcripted (no Whisper/ASR — this tool stays lightweight on purpose).
- Browser-cookie access requires the target browser installed locally; in logged-in sessions YouTube sometimes serves empty format lists to yt-dlp, which is exactly why cookies are the **last** layer (and always paired with `--ignore-no-formats-error`).
- Cache is content-blind: if a video's description/comments change, clear the cache entry.

## License

[MIT](LICENSE) © 2026 JADRT22

"""CLI do yt-transcript: imprime a transcrição no stdout para o agente ler."""

from __future__ import annotations

import argparse
import json
import sys

from .fetch import (
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
        description="Busca a transcrição (legendas) de um vídeo do YouTube. "
        "Útil para agentes de IA lerem o conteúdo do vídeo.",
    )
    parser.add_argument("url", help="URL do vídeo ou ID de 11 caracteres")
    parser.add_argument(
        "-l", "--languages",
        default="pt,pt-BR,en",
        help="Códigos de idioma preferidos, separados por vírgula (padrão: pt,pt-BR,en)",
    )
    parser.add_argument("--json", action="store_true", help="Saída em JSON (metadados + texto)")
    parser.add_argument(
        "--info", action="store_true",
        help="Mostra apenas metadados (título, canal, duração) sem a transcrição",
    )
    parser.add_argument(
        "--desc", action="store_true",
        help="Mostra descrição + comentários do vídeo (JSON). Use com --max-comments",
    )
    parser.add_argument(
        "--max-comments", type=int, default=50, metavar="N",
        help="Número máximo de comentários para --desc (padrão: 50)",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="Lista as legendas disponíveis para o vídeo",
    )
    parser.add_argument(
        "--no-fallback", action="store_true",
        help="Não usa yt-dlp como fallback se a API principal falhar",
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
                print("Nenhuma legenda disponível para este vídeo.")
            else:
                print("Legendas disponíveis:")
                for it in items:
                    tag = " [gerada automaticamente]" if it["is_generated"] else ""
                    print(f"- {it['language']} ({it['language_code']}){tag}")
            return 0

        if args.desc:
            print(json.dumps(get_video_details(args.url, max_comments=args.max_comments), ensure_ascii=False, indent=2))
            return 0

        if args.info:
            print(json.dumps(get_video_info(args.url), ensure_ascii=False, indent=2))
            return 0

        if args.no_fallback:
            from .fetch import extract_video_id, _fetch_via_api

            result = _fetch_via_api(extract_video_id(args.url), langs)
        else:
            result = get_transcript(args.url, langs)

        if args.json:
            print(result_to_json(result))
        else:
            print(result.as_text())
        return 0

    except TranscriptError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

"""Servidor MCP que expõe as ferramentas de transcrição para CLIs de IA.

Compatível com opencode, Claude Code, Freebuff, Cursor, etc.
Rode com: yt-transcript-mcp (ou python -m yt_transcript.mcp_server)
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .fetch import (
    TranscriptError,
    get_transcript,
    get_video_details,
    get_video_info,
    list_available_transcripts,
)

mcp = FastMCP(
    "yt-transcript",
    instructions=(
        "Ferramentas para ler a transcrição (legendas) de vídeos do YouTube. "
        "Aceita URL completa, youtu.be, shorts ou o ID de 11 caracteres. "
        "Use get_transcript para obter o texto do vídeo e resumi-lo/analisá-lo; "
        "use list_transcripts para ver quais idiomas estão disponíveis e "
        "get_video_info para título/canal/duração."
    ),
)

DEFAULT_LANGS = ["pt", "pt-BR", "en"]


@mcp.tool()
def get_transcript_tool(url: str, languages: str | None = None) -> str:
    """Retorna a transcrição completa de um vídeo do YouTube.

    Args:
        url: URL do vídeo (youtube.com/watch?v=..., youtu.be/..., shorts/...) ou ID.
        languages: Códigos de idioma preferidos, separados por vírgula
            (ex.: "pt,en,es"). Padrão: "pt,pt-BR,en".

    Returns:
        Texto da transcrição com um cabeçalho de metadados, ou mensagem de erro.
    """
    langs = [l.strip() for l in languages.split(",") if l.strip()] if languages else DEFAULT_LANGS
    try:
        result = get_transcript(url, langs)
    except TranscriptError as e:
        return f"ERRO: {e}"
    return result.as_text()


@mcp.tool()
def list_transcripts_tool(url: str) -> str:
    """Lista as legendas/transcrições disponíveis para um vídeo (idiomas e tipo)."""
    try:
        items = list_available_transcripts(url)
    except TranscriptError as e:
        return f"ERRO: {e}"
    except Exception as e:
        return f"ERRO: {e}"
    if not items:
        return "Nenhuma legenda disponível para este vídeo."
    lines = [
        f"- {it['language']} ({it['language_code']})"
        f"{' [gerada automaticamente]' if it['is_generated'] else ''}"
        for it in items
    ]
    return "Legendas disponíveis:\n" + "\n".join(lines)


@mcp.tool()
def get_video_info_tool(url: str) -> str:
    """Retorna metadados do vídeo: título, canal, duração e data de upload."""
    try:
        info = get_video_info(url)
    except TranscriptError as e:
        return f"ERRO: {e}"
    except Exception as e:
        return f"ERRO: {e}"
    return json.dumps(info, ensure_ascii=False, indent=2)


@mcp.tool()
def get_video_details_tool(url: str, max_comments: int = 50) -> str:
    """Retorna título, canal, duração, descrição COMPLETA e comentários do vídeo.

    Útil para entender o contexto, links mencionados e a recepção do público.

    Args:
        url: URL do vídeo ou ID.
        max_comments: número máximo de comentários (padrão 50).

    Returns:
        JSON com description e lista de comments (autor, texto, likes).
    """
    try:
        details = get_video_details(url, max_comments=max_comments)
    except TranscriptError as e:
        return f"ERRO: {e}"
    except Exception as e:
        return f"ERRO: {e}"
    return json.dumps(details, ensure_ascii=False, indent=2)


def main() -> None:
    """Ponto de entrada do servidor MCP (stdio)."""
    mcp.run()


if __name__ == "__main__":
    main()

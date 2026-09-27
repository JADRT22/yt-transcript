# yt-transcript

Ferramenta para agentes de IA lerem a **transcrição (legendas) de vídeos do YouTube**.

- **CLI** (`yt-transcript`): imprime a transcrição no stdout — qualquer agente que roda comandos consegue ler.
- **Servidor MCP** (`yt-transcript-mcp`): expõe ferramentas nativas para CLIs compatíveis com MCP (opencode, Claude Code, Freebuff, Cursor, etc.).

O resumo/análise fica por conta do modelo do agente — esta ferramenta só entrega o texto da transcrição.

## Instalação

```bash
cd yt-transcript
python3 -m venv .venv
.venv/bin/pip install -e .
```

## Uso via CLI

```bash
# Transcrição completa (idiomas: pt, pt-BR, en por padrão)
.venv/bin/yt-transcript "https://www.youtube.com/watch?v=VIDEO_ID"

# Metadados (título, canal, duração)
.venv/bin/yt-transcript VIDEO_ID --info

# Legendas disponíveis
.venv/bin/yt-transcript VIDEO_ID --list

# Saída em JSON
.venv/bin/yt-transcript VIDEO_ID --json

# Outros idiomas
.venv/bin/yt-transcript VIDEO_ID -l en,es

# Descrição + comentários do vídeo (JSON)
.venv/bin/yt-transcript VIDEO_ID --desc
.venv/bin/yt-transcript VIDEO_ID --desc --max-comments 100
```

Aceita `youtube.com/watch?v=...`, `youtu.be/...`, `youtube.com/shorts/...` ou o ID de 11 caracteres.

## Integração com agentes

### Servidor MCP (stdio)

Comando: `CAMINHO_ABSOLUTO/yt-transcript/.venv/bin/yt-transcript-mcp`

#### opencode

Em `~/.config/opencode/opencode.json` (ou `opencode.json` do projeto):

```json
{
  "mcp": {
    "yt-transcript": {
      "type": "local",
      "command": ["/caminho/absoluto/yt-transcript/.venv/bin/yt-transcript-mcp"],
      "enabled": true
    }
  }
}
```

#### Claude Code

```bash
claude mcp add yt-transcript -- /caminho/absoluto/yt-transcript/.venv/bin/yt-transcript-mcp
```

#### Codebuff / Freebuff

Em `.codebuff/config.json` (mcps):

```json
{
  "mcps": {
    "yt-transcript": {
      "command": "/caminho/absoluto/yt-transcript/.venv/bin/yt-transcript-mcp",
      "cwd": "/caminho/absoluto/yt-transcript"
    }
  }
}
```

#### Freebuff (e outros agentes com `mcp.json`)

Na raiz do projeto onde roda o agente, crie um `mcp.json`:

```json
{
  "mcpServers": {
    "yt-transcript": {
      "command": "/caminho/absoluto/yt-transcript/.venv/bin/yt-transcript-mcp"
    }
  }
}
```

Ou, sem MCP: basta pedir ao agente para rodar
`/caminho/absoluto/yt-transcript/.venv/bin/yt-transcript <URL>` e ler a saída.

### Ferramentas expostas via MCP

| Ferramenta | Descrição |
|---|---|
| `get_transcript_tool(url, languages?)` | Transcrição completa do vídeo |
| `list_transcripts_tool(url)` | Idiomas/legendas disponíveis |
| `get_video_info_tool(url)` | Título, canal, duração, data de upload |
| `get_video_details_tool(url, max_comments?)` | **Descrição completa + comentários** (autor, texto, likes) |

## Como funciona

A busca da transcrição tenta em cascata:

1. **youtube-transcript-api** (legendas manuais e automáticas, sem chave de API)
2. **yt-dlp** client padrão (web)
3. **yt-dlp** client `android` (bypassa a checagem anti-bot "confirm you're not a bot")
4. **yt-dlp + cookies do navegador** (cura bloqueio de IP / erro 429)

Os metadados e a lista de legendas usam a mesma cascata de fallbacks.

### Cookies do navegador (última linha de defesa)

Por padrão usa o perfil padrão do **Firefox**. Configurável via variável de ambiente:

```bash
export YT_TRANSCRIPT_COOKIES_BROWSER=firefox   # padrão; ou chrome, chromium, brave...
export YT_TRANSCRIPT_COOKIES_BROWSER=none      # desativa o uso de cookies
```

Obs.: em sessões logadas o YouTube às vezes retorna "formatos vazios" pro yt-dlp; por isso os cookies são a **última** tentativa, e vêm sempre com `--ignore-no-formats-error`.

### Cache em disco

Transcrições, metadados e listas de legendas são cacheados em `~/.cache/yt-transcript/` — a 2ª chamada do mesmo vídeo é ~10x mais rápida e não consome rate limit.

```bash
export YT_TRANSCRIPT_CACHE=~/.cache/yt-transcript   # padrão
export YT_TRANSCRIPT_CACHE=none                     # desativa (sempre busca na rede)
```

Para forçar uma busca nova de um vídeo específico, remova o arquivo correspondente do diretório de cache (nomes em hash SHA-256).

## Limitações

- Vídeos **sem legendas** não têm transcrição disponível (não usa Whisper/ASR — o foco é ser leve).
- Vídeos muito longos (>1h) geram textos grandes; o agente pode pedir trechos ou resumir por partes.
- YouTube pode bloquear IPs de datacenter com rate limit; em máquina local costuma funcionar bem.

# LlamaDeck

Web UI for managing Ollama models — list, import GGUF, pull from registry/HuggingFace, inspect, and delete. Runs as a standalone server on its own port.

## Features

- **List models** — name, family, parameter count, quantization, size
- **Import GGUF** — browser upload or path-based import, with auto-suggest naming and conflict detection
- **Delete** — with confirmation
- **Inspect** — view modelfile via `ollama show`
- **Pull from registry** — pull models from Ollama's library
- **Pull from HuggingFace** — paste a download URL, optional API key for gated models
- **GGUF library** — browse local GGUF files with auto-detected metadata (family, parameter count, quantization, context length, model name) and import with one click
- **Sortable columns** — click any column header in the models table to sort by name, family, params, quantization, or size
- **GGUF header parsing** — extracts quantization, architecture family, parameter count, context length, and model name directly from GGUF file metadata without importing
- **Multiple instances** — register local, Docker, or remote Ollama instances
- **Auto-discovery** — detects running Ollama Docker containers and local installs
- **Background tasks** — long operations (pull, import) run asynchronously with status polling
- **Encrypted credentials** — API keys stored in SQLite with Fernet encryption at rest

## Prerequisites

- **Ollama** must be installed and running (`ollama serve`). Get it at [ollama.com](https://ollama.com).
- Python 3.10+

## Quick Start

```bash
pip install -r requirements.txt
python -m backend.main
```

Open http://localhost:11435

### Docker

```bash
cp .env.example .env   # edit platform-specific settings if needed
docker compose up -d
```

An Ollama container must also be running on the same host for the manager to discover. The manager connects via the Docker socket to discover and communicate with sibling Ollama containers.
On Windows, use **WSL 2** — `/var/run/docker.sock` is available there natively.
Native Windows (Docker Desktop named pipes) is **not supported** for Docker socket discovery; register Ollama as a remote instance instead.

## Configuration

| Method | Example |
|---|---|
| CLI flags | `python -m backend.main --port 8080 --host 127.0.0.1` |
| Environment | `OLLAMA_MANAGER_HOST=0.0.0.0 OLLAMA_MANAGER_PORT=11435` |
| Config file | `~/.config/ollama-manager/config.json` |

## Architecture

```
Browser → FastAPI + SPA (port 11435) → [docker exec | local ollama | HTTP API] → Ollama
```

- **Backend**: Python/FastAPI with async endpoints and background task workers
- **Frontend**: Vanilla JS SPA served by FastAPI (dark theme)
- **Persistence**: SQLite for instances, separate encrypted SQLite for credentials
- **Credentials**: Stored in `~/.config/ollama-manager/credentials.db`, encrypted with Fernet + PBKDF2, file permissions 600

### Instance Types

| Type | Discovery | GGUF Import |
|---|---|---|
| **Local** | `ollama` on PATH | Direct filesystem access |
| **Docker** | `docker ps` scan | Shared volume path (preferred) or `docker cp` fallback |
| **Remote** | Manual URL + API key | Not supported |

## API Overview

| Endpoint | Description |
|---|---|
| `GET /api/instances` | List registered instances |
| `GET /api/instances/discover` | Auto-discover local/docker instances |
| `GET /api/models/{id}` | List models for an instance (sortable columns in UI) |
| `POST /api/pull/registry` | Pull from Ollama registry (async, returns task_id) |
| `POST /api/pull/huggingface` | Pull from HuggingFace URL (async) |
| `POST /api/import/upload` | Upload and import GGUF file (async) |
| `POST /api/gguf-library/import` | Import from library (async) |
| `GET /api/tasks/{id}` | Poll task status |
| `PUT /api/credentials` | Store an API key |

## License

Apache 2.0

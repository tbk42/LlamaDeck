# LlamaDeck — Requirements

Build a fully functional web UI for managing Ollama models — Runs independently on its own port/entrypoint.

## Core Features

- **List models** — show all Ollama models with name, size, quantization, family, parameter count
- **Import GGUF** — browser file picker uploads .gguf to a temp directory, auto-suggest name, check for naming conflicts, run `ollama create` (locally if Ollama is running locally, or via `docker exec` if in a container)
- **Delete** — working delete with confirmation
- **Inspect** — show modelfile, parameters, details via `ollama show`
- **Pull from registry** — pull models from Ollama's library
- **Pull from HuggingFace** — paste a HuggingFace download URL and pull the model, user-supplied API key optional
- **GGUF library** — browse your local GGUF directory with buttons to import into Ollama (convenience/conservation of bandwidth)

## Warnings

- GGUF library feature can quickly consume large amounts of local storage, use with caution
- Pulling models from Ollama registry or HuggingFace can download 10–40GB+ files — same storage concern applies

## Architecture

- Standalone web app with its own HTTP server and frontend SPA, served on a dedicated port
- Backend API: wraps `docker exec` commands for containerized Ollama, and wraps local `ollama` commands for local installs
- Support for registering multiple Ollama instances to select from

### Instance Discovery & Persistence

- **Docker**: scan running containers for the `ollama` image → auto-configure
- **Local**: check if `ollama` is on PATH → auto-configure
- **Remote**: user provides URL + optional API key manually
- **Persistence**: registered instances stored in SQLite

### API Key Storage

- API keys (HuggingFace, remote Ollama instances) stored in a dedicated config file at `~/.config/ollama-manager/credentials.json`
- File permissions set to `600` (owner read/write only)
- Encryption at rest is best-effort (future enhancement: OS keychain integration via libsecret/Keychain)

### Port Configuration

- Default port: `11435`
- Configurable via command-line flag or config file

### HuggingFace Integration

- No search UI — user pastes a HuggingFace download URL directly
- Optional API key for gated models or rate limit increases

## Context

- Detect Ollama instances among docker containers
- Support for registering multiple Ollama instances to select from (containerized via docker, local install, remote hosts). Tracks current models and GGUF directory per instance.
- The `docker exec` pattern is used for communicating with containerized Ollama instances

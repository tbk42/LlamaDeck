# Changelog

## [1.0.0] — 2026-07-14

Initial release.

### Added

- List Ollama models with name, family, parameter count, quantization, size
- Import GGUF via browser upload or filesystem path
- Delete models with confirmation dialog
- Inspect models (view modelfile via `ollama show`)
- Pull models from Ollama registry
- Pull models from HuggingFace (URL-based, optional API key)
- GGUF library browser — browse local `.gguf` files and import
- Multiple instance support (local, Docker, remote)
- Auto-discovery of Docker containers and local `ollama` installs
- Instance CRUD with SQLite persistence
- Encrypted credential storage (Fernet + PBKDF2, SQLite, `chmod 600`)
- Background task system for long-running operations (pull, import)
- Dark-theme single-page application frontend
- Configurable port/host via CLI flags, environment variables, or config file
- Docker support with socket-based container discovery and `docker cp` fallback

### Fixed

- HuggingFace download temp file leak on HTTP error (wrapped in `try/finally`)
- Model DELETE request body not being sent (frontend `API.del` signature)
- OOM risk on GGUF upload (streamed in 1MB chunks instead of `file.read()`)
- TOCTOU race on credential storage (moved from JSON to transactional SQLite)
- Docker GGUF import not mounting the `.gguf` file (hybrid: shared volume path or `docker cp`)
- Self-circular import in `pull_from_huggingface`
- Deprecated `on_event` lifespan pattern (migrated to FastAPI lifespan context manager)
- Dockerfile dependency drift (now uses `requirements.txt`)
- Docker compose env vars not wired to app config

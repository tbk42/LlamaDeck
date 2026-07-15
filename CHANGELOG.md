# Changelog

## [Unreleased]

## [0.1.1] - 2026-07-15

### Changed
- Repository fully rewritten with new project name
- Git history cleaned: no traces of old project name in any commit
- Docker image now published as `ghcr.io/tbk42/llamadeck`

## [0.1.0] - 2026-07-15

### Added
- GGUF header parsing — quantization, family, parameter size, model name, and context length extracted directly from GGUF files without importing
- GGUF library cards now show metadata: model name, family, parameter count, quantization, and context length in a structured layout
- Sortable columns in the models table — click Name, Family, Params, Quantization, or Size headers to sort
- Parameter count estimation from architecture metadata when `general.size_label` is missing (handles dense and MoE architectures)
- Context length detection from architecture-specific metadata keys
- `.env.example` with documented `DOCKER_SOCKET` variable for cross-platform socket paths
- First-run welcome dialog when no instances are registered (Auto-Discover / Add Manually / Skip)
- Unit tests (45 tests) for `gguf_parser.py` and `suggest_name()`
- CI workflow (`.github/workflows/test.yml`) — runs tests on push/PR for Python 3.10 and 3.12
- Release workflow (`.github/workflows/release.yml`) — tag `v*` triggers Docker build, GHCR push, and GitHub Release
- GitHub community files: issue templates, PR template, contributing guide

### Changed
- GGUF upload now streams directly to the final destination file, eliminating temporary file double-write
- GGUF library card layout redesigned with filename/size top row, model name/family middle row, and params/quant/context info row
- Enhanced `list_gguf_files()` endpoint returns richer metadata per file
- `list_gguf_files()` now prefers `container_gguf_dir` over `gguf_dir` when set, so Docker instances resolve GGUF paths correctly
- Size column in models table now includes the unit (GB/MB) parsed from `ollama list` text output
- **Portability fixes for fresh clones:**
  - Upload temp directory now uses system default (`tempfile.gettempdir()`) instead of hardcoded `/unified/tmp` — override via `TMPDIR`/`TEMP` env var
  - DEFAULT_GGUF_DIR changed from `Path.cwd() / "GGUF Models"` to `Path.home() / "GGUF-Models"` (predictable, cross-platform)
  - Docker compose GGUF volume changed from `/unified/GGUF Models` to `./GGUF-Models` (relative to project)
  - Docker socket path made configurable via `DOCKER_SOCKET` env var, with platform defaults documented in `.env.example`
  - Removed dead `_get_machine_secret()` function from credential store (encryption uses a stored random secret, not machine-id)
- Ollama/Docker error messages now show clear suggestions instead of raw `FileNotFoundError` → 500
- Windows guidance updated: WSL 2 supported, native Docker Desktop named pipes not

### Fixed
- GGUF upload failing with "No space left on device" when `/tmp` partition was too small
- GGUF upload failing with "There was an error parsing the body" due to missing `python-multipart` dependency in server runtime
- GGUF array metadata parsing in header reader (handles typed arrays correctly without desync)
- GGUF metadata fallback from filename when file_type header values don't match known quantization labels
- Multipart parser ignoring form fields (instance_id, model_name) sent after the file field — `is_file_part` flag now resets per-part instead of relying on global `dest_file` state
- Docker auto-discover failing inside container because `docker` CLI was not installed — added `docker-cli` package to Dockerfile
- GGUF Library returning no files from Docker because host `gguf_dir` path was inaccessible — now uses `container_gguf_dir` when available
- Models table size column missing units (e.g., "5.1" instead of "5.1 GB")
- HuggingFace pull using temp file path as model name — now extracts name from GGUF metadata or URL filename
- `requirements.md` reference to non-existent `/unified/GGUF Models/import.sh`
- `.env` added to `.gitignore` to prevent accidental secret commits
- `AGENTS.md` removed from repo (git-ignored) to avoid confusing end users
- `.dockerignore` added to exclude `.venv/`, `__pycache__/`, `.git/` from Docker build context
- Dependency list removed from `pyproject.toml` — `requirements.txt` is now the single source of truth for deps
- `_normalize_arch()` incorrectly matched `qwen2` as `qwen2moe` — now checks exact matches before prefix matches
- `_normalize_arch()` failed to match `command_r` (underscore in known name) — now normalizes both sides of comparison

[0.1.1]: https://github.com/tbk42/LlamaDeck/releases/tag/v0.1.1
[0.1.0]: https://github.com/tbk42/LlamaDeck/releases/tag/v0.1.0

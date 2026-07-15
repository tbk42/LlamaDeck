# Changelog

## [Unreleased]

### Added
- GGUF header parsing — quantization, family, parameter size, model name, and context length extracted directly from GGUF files without importing
- GGUF library cards now show metadata: model name, family, parameter count, quantization, and context length in a structured layout
- Sortable columns in the models table — click Name, Family, Params, Quantization, or Size headers to sort
- Parameter count estimation from architecture metadata when `general.size_label` is missing (handles dense and MoE architectures)
- Context length detection from architecture-specific metadata keys
- `.env.example` with documented `DOCKER_SOCKET` variable for cross-platform socket paths

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

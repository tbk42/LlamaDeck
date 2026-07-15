# Changelog

## [Unreleased]

### Added
- GGUF header parsing — quantization, family, parameter size, model name, and context length extracted directly from GGUF files without importing
- GGUF library cards now show metadata: model name, family, parameter count, quantization, and context length in a structured layout
- Sortable columns in the models table — click Name, Family, Params, Quantization, or Size headers to sort
- Parameter count estimation from architecture metadata when `general.size_label` is missing (handles dense and MoE architectures)
- Context length detection from architecture-specific metadata keys

### Changed
- GGUF upload now streams directly to the final destination file, eliminating temporary file double-write
- Upload temp directory moved to `/unified/tmp` to avoid disk space issues on small tmpfs partitions
- GGUF library card layout redesigned with filename/size top row, model name/family middle row, and params/quant/context info row
- Enhanced `list_gguf_files()` endpoint returns richer metadata per file

### Fixed
- GGUF upload failing with "No space left on device" when `/tmp` partition was too small
- GGUF upload failing with "There was an error parsing the body" due to missing `python-multipart` dependency in server runtime
- GGUF array metadata parsing in header reader (handles typed arrays correctly without desync)
- GGUF metadata fallback from filename when file_type header values don't match known quantization labels

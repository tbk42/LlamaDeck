import struct
import tempfile
from pathlib import Path

import pytest

from backend.services.gguf_parser import (
    GGUF_MAGIC,
    read_gguf_meta,
    _extract_quantization,
    _normalize_arch,
    _parse_filename_quant,
    _estimate_params,
)


# ---------------------------------------------------------------------------
# helpers for building synthetic GGUF binaries
# ---------------------------------------------------------------------------

def _pack_str(s: str) -> bytes:
    raw = s.encode("utf-8")
    return struct.pack("<Q", len(raw)) + raw


def _pack_kv(key: str, vtype: int, val: bytes) -> bytes:
    return _pack_str(key) + struct.pack("<I", vtype) + val


def _make_gguf(kv_pairs: list[tuple[str, int, bytes]]) -> bytes:
    buf = struct.pack("<I", GGUF_MAGIC)
    buf += struct.pack("<I", 3)  # version
    buf += struct.pack("<Q", 0)  # tensor_count
    buf += struct.pack("<Q", len(kv_pairs))
    for k, t, v in kv_pairs:
        buf += _pack_kv(k, t, v)
    return buf


def _write_gguf(kv_pairs: list[tuple[str, int, bytes]]) -> str:
    data = _make_gguf(kv_pairs)
    tmp = tempfile.NamedTemporaryFile(suffix=".gguf", delete=False)
    tmp.write(data)
    tmp.close()
    return tmp.name


def _str_val(s: str) -> bytes:
    return _pack_str(s)


def _u32_val(v: int) -> bytes:
    return struct.pack("<I", v)


def _u64_val(v: int) -> bytes:
    return struct.pack("<Q", v)


def _bool_val(v: bool) -> bytes:
    return struct.pack("?", v)


# ---------------------------------------------------------------------------
# _parse_filename_quant
# ---------------------------------------------------------------------------

class TestParseFilenameQuant:
    def test_q4_k_m(self):
        assert _parse_filename_quant("model-q4_k_m.gguf") == "Q4_K_M"

    def test_q5_k_m(self):
        assert _parse_filename_quant("model-Q5_K_M.gguf") == "Q5_K_M"

    def test_q2_k(self):
        assert _parse_filename_quant("model-q2_k.gguf") == "Q2_K"

    def test_q6_k(self):
        assert _parse_filename_quant("model-q6_k.gguf") == "Q6_K"

    def test_iq4_xs(self):
        assert _parse_filename_quant("model-iq4_xs.gguf") == "IQ4_XS"

    def test_fp16(self):
        assert _parse_filename_quant("model-fp16.gguf") == "FP16"

    def test_fp32(self):
        assert _parse_filename_quant("model-fp32.gguf") == "FP32"

    def test_no_match(self):
        assert _parse_filename_quant("model.gguf") is None

    def test_no_extension(self):
        assert _parse_filename_quant("q4_k_m") == "Q4_K_M"


# ---------------------------------------------------------------------------
# _extract_quantization
# ---------------------------------------------------------------------------

class TestExtractQuantization:
    def test_from_file_type_only(self):
        meta = {"general.file_type": 28}
        assert _extract_quantization(meta, "whatever.gguf") == "Q4_K_M"

    def test_file_type_and_filename_agree(self):
        meta = {"general.file_type": 28}
        assert _extract_quantization(meta, "model-q4_k_m.gguf") == "Q4_K_M"

    def test_filename_takes_precedence_when_disagreeing(self):
        meta = {"general.file_type": 28}  # Q4_K_M
        result = _extract_quantization(meta, "model-q2_k.gguf")
        assert result == "Q2_K"

    def test_no_file_type_falls_to_filename(self):
        meta = {}
        assert _extract_quantization(meta, "model-q5_k_m.gguf") == "Q5_K_M"

    def test_no_metadata_no_filename(self):
        assert _extract_quantization({}, "model.gguf") is None


# ---------------------------------------------------------------------------
# _normalize_arch
# ---------------------------------------------------------------------------

class TestNormalizeArch:
    def test_llama(self):
        assert _normalize_arch("llama") == "llama"

    def test_qwen2(self):
        assert _normalize_arch("qwen2") == "qwen2"

    def test_qwen2_from_qwen2moe(self):
        assert _normalize_arch("qwen2moe") == "qwen2moe"

    def test_underscores_stripped(self):
        assert _normalize_arch("deep_seek2") == "deepseek2"

    def test_hyphens_stripped(self):
        assert _normalize_arch("command-r") == "command_r"

    def test_partial_match(self):
        assert _normalize_arch("mixtral") == "mixtral"

    def test_unknown_arch(self):
        assert _normalize_arch("foobar") == "foobar"


# ---------------------------------------------------------------------------
# _estimate_params
# ---------------------------------------------------------------------------

class TestEstimateParams:
    def test_simple_dense_7b(self):
        meta = {
            "general.architecture": "llama",
            "llama.embedding_length": 4096,
            "llama.block_count": 32,
            "llama.attention.head_count": 32,
            "llama.attention.key_length": 128,
            "llama.feed_forward_length": 11008,
            "llama.vocab_size": 32000,
        }
        result = _estimate_params(meta)
        assert result is not None
        assert "B" in result or "M" in result

    def test_missing_fields_returns_none(self):
        assert _estimate_params({"general.architecture": "llama"}) is None

    def test_moe_architecture(self):
        meta = {
            "general.architecture": "mixtral",
            "mixtral.embedding_length": 4096,
            "mixtral.block_count": 32,
            "mixtral.attention.head_count": 32,
            "mixtral.attention.head_count_kv": 8,
            "mixtral.attention.key_length": 128,
            "mixtral.feed_forward_length": 14336,
            "mixtral.vocab_size": 32000,
            "mixtral.leading_dense_block_count": 0,
            "mixtral.expert_count": 8,
            "mixtral.expert_feed_forward_length": 14336,
        }
        result = _estimate_params(meta)
        assert result is not None


# ---------------------------------------------------------------------------
# read_gguf_meta — integration tests with real binary files
# ---------------------------------------------------------------------------

class TestReadGgufMeta:
    def test_non_existent_file(self):
        assert read_gguf_meta("/nonexistent/file.gguf") == {}

    def test_too_small_file(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".gguf", delete=False)
        tmp.write(b"too small")
        tmp.close()
        try:
            assert read_gguf_meta(tmp.name) == {}
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    def test_invalid_magic(self):
        data = b"\x00" * 32
        tmp = tempfile.NamedTemporaryFile(suffix=".gguf", delete=False)
        tmp.write(data)
        tmp.close()
        try:
            assert read_gguf_meta(tmp.name) == {}
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    def test_metadata_string_values(self):
        kv = [
            ("general.architecture", 8, _str_val("llama")),
            ("general.name", 8, _str_val("Llama 3.2 3B")),
        ]
        path = _write_gguf(kv)
        try:
            meta = read_gguf_meta(path)
            assert meta.get("general.architecture") == "llama"
            assert meta.get("general.name") == "Llama 3.2 3B"
            assert meta.get("gguf_version") == 3
            assert meta.get("family") == "llama"
            assert meta.get("label") == "Llama 3.2 3B"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_uint32_values(self):
        kv = [
            ("general.architecture", 8, _str_val("llama")),
            ("llama.context_length", 4, _u32_val(8192)),
            ("general.file_type", 4, _u32_val(28)),
        ]
        path = _write_gguf(kv)
        try:
            meta = read_gguf_meta(path)
            assert meta.get("llama.context_length") == 8192
            assert meta.get("general.file_type") == 28
            assert meta.get("context_length") == 8192
            assert meta.get("quantization") == "Q4_K_M"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_bool_value(self):
        kv = [
            ("general.architecture", 8, _str_val("llama")),
            ("test.bool", 7, _bool_val(True)),
        ]
        path = _write_gguf(kv)
        try:
            meta = read_gguf_meta(path)
            assert meta.get("test.bool") is True
        finally:
            Path(path).unlink(missing_ok=True)

    def test_array_metadata(self):
        arr_type = 4  # uint32
        arr_len = 3
        arr_data = struct.pack("<III", 100, 200, 300)
        arr_val = struct.pack("<I", arr_type) + struct.pack("<Q", arr_len) + arr_data
        kv = [
            ("general.architecture", 8, _str_val("llama")),
            ("test.array", 9, arr_val),
        ]
        path = _write_gguf(kv)
        try:
            meta = read_gguf_meta(path)
            assert meta.get("test.array") == [100, 200, 300]
        finally:
            Path(path).unlink(missing_ok=True)

    def test_dense_parameter_estimate(self):
        kv = [
            ("general.architecture", 8, _str_val("llama")),
            ("llama.embedding_length", 4, _u32_val(4096)),
            ("llama.block_count", 4, _u32_val(32)),
            ("llama.attention.head_count", 4, _u32_val(32)),
            ("llama.attention.key_length", 4, _u32_val(128)),
            ("llama.feed_forward_length", 4, _u32_val(11008)),
            ("llama.vocab_size", 4, _u32_val(32000)),
        ]
        path = _write_gguf(kv)
        try:
            meta = read_gguf_meta(path)
            assert meta.get("parameter_size") is not None
            assert "B" in meta["parameter_size"] or "M" in meta["parameter_size"]
        finally:
            Path(path).unlink(missing_ok=True)

    def test_moe_parameter_estimate(self):
        kv = [
            ("general.architecture", 8, _str_val("mixtral")),
            ("mixtral.embedding_length", 4, _u32_val(4096)),
            ("mixtral.block_count", 4, _u32_val(32)),
            ("mixtral.attention.head_count", 4, _u32_val(32)),
            ("mixtral.attention.head_count_kv", 4, _u32_val(8)),
            ("mixtral.attention.key_length", 4, _u32_val(128)),
            ("mixtral.feed_forward_length", 4, _u32_val(14336)),
            ("mixtral.vocab_size", 4, _u32_val(32000)),
            ("mixtral.leading_dense_block_count", 4, _u32_val(0)),
            ("mixtral.expert_count", 4, _u32_val(8)),
            ("mixtral.expert_feed_forward_length", 4, _u32_val(14336)),
        ]
        path = _write_gguf(kv)
        try:
            meta = read_gguf_meta(path)
            assert meta.get("parameter_size") is not None
            assert "B" in meta["parameter_size"]
        finally:
            Path(path).unlink(missing_ok=True)

    def test_context_length_from_key(self):
        kv = [
            ("general.architecture", 8, _str_val("llama")),
            ("llama.context_length", 4, _u32_val(131072)),
        ]
        path = _write_gguf(kv)
        try:
            meta = read_gguf_meta(path)
            assert meta.get("context_length") == 131072
        finally:
            Path(path).unlink(missing_ok=True)

    def test_size_label_fallback(self):
        kv = [
            ("general.architecture", 8, _str_val("llama")),
            ("general.size_label", 8, _str_val("7B")),
        ]
        path = _write_gguf(kv)
        try:
            meta = read_gguf_meta(path)
            assert meta.get("parameter_size") == "7B"
        finally:
            Path(path).unlink(missing_ok=True)

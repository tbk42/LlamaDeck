from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Any

GGUF_MAGIC = 0x46554747  # "GGUF" little-endian

# https://github.com/ggerganov/ggml/blob/master/docs/gguf.md
FILE_TYPE_MAP = {
    0: "FP32",
    1: "FP16",
    2: "Q4_0",
    3: "Q4_1",
    6: "Q5_0",
    7: "Q5_1",
    8: "Q8_0",
    12: "Q2_K",
    13: "Q3_K_S",
    14: "Q4_K_S",
    15: "Q5_K_S",
    16: "Q6_K",
    17: "Q8_K",
    18: "IQ1_S",
    19: "IQ2_XXS",
    20: "IQ2_XS",
    21: "IQ3_XXS",
    22: "IQ1_M",
    23: "IQ4_NL",
    24: "IQ3_S",
    25: "IQ2_S",
    26: "IQ4_XS",
    27: "IQ3_M",
    28: "Q4_K_M",
    29: "Q4_K_S",
    30: "Q5_K_M",
    31: "Q5_K_S",
    32: "Q6_K",
    33: "W8A16",
    34: "Q3_K_M",
    35: "Q3_K_L",
    36: "Q4_K_L",
    37: "Q5_K_L",
}

ARCH_MAP = {
    "llama", "falcon", "bert", "gpt2", "gptj", "gptneox", "mpt", "starcoder",
    "baichuan", "qwen", "qwen2", "qwen2moe", "phi2", "phi3", "plamo",
    "codeshell", "orminer", "gemma", "gemma2", "starcoder2", "cohere",
    "chatglm", "minicpm", "minicpm3", "deepseek2", "command_r",
    "dbrx", "olmo", "openelm", "arctic", "deepseek3", "bitnet",
    "t5", "t5encoder", "granite", "granitemoe", "chameleon",
    "mistral", "mixtral", "nemotron",
}


def read_gguf_meta(path: str | Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    p = Path(path)
    if not p.exists() or p.stat().st_size < 32:
        return result

    with open(p, "rb") as f:
        magic = struct.unpack("<I", f.read(4))[0]
        if magic != GGUF_MAGIC:
            return result

        version = struct.unpack("<I", f.read(4))[0]
        result["gguf_version"] = version

        tensor_count = struct.unpack("<Q", f.read(8))[0]
        kv_count = struct.unpack("<Q", f.read(8))[0]

        for _ in range(kv_count):
            key = _read_string(f)
            val = _read_value(f)
            result[key] = val

    quantization = _extract_quantization(result, p.name)
    if quantization:
        result["quantization"] = quantization

    architecture = result.get("general.architecture")
    if architecture:
        result["family"] = _normalize_arch(architecture)

    name_label = result.get("general.name") or result.get("general.filename")
    if name_label:
        result["label"] = name_label

    size = _estimate_params(result)
    if size is None:
        raw = result.get("general.size_label")
        if raw and re.match(r"^\d+[.]?\d*[BMK]$", str(raw)):
            size = str(raw)
    if size:
        result["parameter_size"] = size

    ctx = result.get("general.context_length")
    if ctx is None:
        for k, v in result.items():
            if k.endswith(".context_length") and isinstance(v, int):
                ctx = v
                break
    if ctx:
        result["context_length"] = ctx

    return result


# Common quantization patterns found in GGUF filenames
_QUANT_PATTERNS = [
    r'(?i)(q[0-9]_[kmls](?:_[km])?)',
    r'(?i)(iq[0-9]_[a-z]+)',
    r'(?i)(fp(?:16|32))',
    r'(?i)(q(?:2|3|4|5|6|8)_(?:[kmls](?:_[mxl])?|[012]))',
]

def _extract_quantization(meta: dict, filename: str) -> str | None:
    file_type = meta.get("general.file_type")
    if file_type is not None and isinstance(file_type, int):
        mapped = FILE_TYPE_MAP.get(file_type)
        name_quant = _parse_filename_quant(filename)
        if mapped and mapped == name_quant:
            return mapped
        if mapped and name_quant is None:
            return mapped

    return _parse_filename_quant(filename)

def _parse_filename_quant(filename: str) -> str | None:
    name = filename.replace(".gguf", "").replace(".GGUF", "")
    for pat in _QUANT_PATTERNS:
        m = re.search(pat, name)
        if m:
            return m.group(1).upper()
    return None


def _get(meta: dict, key: str):
    for k, v in meta.items():
        if k == key or k.endswith("." + key):
            return v
    return None

def _estimate_params(meta: dict) -> str | None:
    arch = meta.get("general.architecture", "")
    d = meta.get(f"{arch}.embedding_length") or _get(meta, "embedding_length")
    n_layers = meta.get(f"{arch}.block_count") or _get(meta, "block_count")
    n_heads = meta.get(f"{arch}.attention.head_count") or _get(meta, "head_count")
    n_kv = meta.get(f"{arch}.attention.head_count_kv") or _get(meta, "head_count_kv") or n_heads
    head_dim = meta.get(f"{arch}.attention.key_length") or _get(meta, "key_length")
    ffn = meta.get(f"{arch}.feed_forward_length") or _get(meta, "feed_forward_length")
    vocab = meta.get(f"{arch}.vocab_size") or _get(meta, "vocab_size")

    if not all([d, n_layers, n_heads, ffn, vocab]):
        return None
    if not head_dim:
        head_dim = d // n_heads

    qkv = d * n_heads * head_dim + 2 * d * n_kv * head_dim
    o = n_heads * head_dim * d
    attention = qkv + o
    mlp = 3 * d * ffn
    norms = 2 * d
    per_layer = attention + mlp + norms

    n_dense = meta.get(f"{arch}.leading_dense_block_count") or 0
    if n_dense and n_dense < n_layers:
        n_moe = n_layers - n_dense
        e_ffn = meta.get(f"{arch}.expert_feed_forward_length") or _get(meta, "expert_feed_forward_length")
        n_exp = meta.get(f"{arch}.expert_count") or _get(meta, "expert_count") or 1
        n_shared = meta.get(f"{arch}.expert_shared_count") or 0
        if e_ffn:
            moe_ffn = n_exp * 3 * d * e_ffn + n_shared * 3 * d * (e_ffn if n_shared else 0)
            per_layer_moe = attention + moe_ffn + norms
            total = n_dense * per_layer + n_moe * per_layer_moe
        else:
            total = n_layers * per_layer
    else:
        total = n_layers * per_layer

    embed = vocab * d
    lm_head = vocab * d
    final_norm = d
    total += embed + lm_head + final_norm

    if total >= 1e9:
        val = total / 1e9
        label = "B"
    elif total >= 1e6:
        val = total / 1e6
        label = "M"
    else:
        return None

    if val < 10:
        return f"{val:.1f}{label}"
    return f"{round(val)}{label}"


def _read_string(f) -> str:
    length = struct.unpack("<Q", f.read(8))[0]
    return f.read(length).decode("utf-8", errors="replace")


def _read_typed_value(f, value_type):
    if value_type == 0:
        return struct.unpack("<B", f.read(1))[0]
    elif value_type == 1:
        return struct.unpack("<b", f.read(1))[0]
    elif value_type == 2:
        return struct.unpack("<H", f.read(2))[0]
    elif value_type == 3:
        return struct.unpack("<h", f.read(2))[0]
    elif value_type == 4:
        return struct.unpack("<I", f.read(4))[0]
    elif value_type == 5:
        return struct.unpack("<i", f.read(4))[0]
    elif value_type == 6:
        return struct.unpack("<f", f.read(4))[0]
    elif value_type == 7:
        return struct.unpack("?", f.read(1))[0]
    elif value_type == 8:
        return _read_string(f)
    elif value_type == 10:
        return struct.unpack("<Q", f.read(8))[0]
    elif value_type == 11:
        return struct.unpack("<q", f.read(8))[0]
    elif value_type == 12:
        return struct.unpack("<d", f.read(8))[0]
    return None

def _read_value(f):
    value_type = struct.unpack("<I", f.read(4))[0]
    if value_type == 9:
        arr_type = struct.unpack("<I", f.read(4))[0]
        arr_len = struct.unpack("<Q", f.read(8))[0]
        return [_read_typed_value(f, arr_type) for _ in range(arr_len)]
    return _read_typed_value(f, value_type)


def _normalize_arch(arch: str) -> str:
    arch = arch.lower().replace("-", "").replace("_", "")
    for known in ARCH_MAP:
        if arch == known:
            return known
        if known.startswith(arch) or arch.startswith(known):
            return known
    return arch

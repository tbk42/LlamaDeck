from __future__ import annotations

import shutil
import subprocess
import uuid
from typing import Any

from backend.database import get_db
from backend.services.ollama_client import OllamaClient


def _detect_container_mounts(container_id: str) -> tuple[str | None, str | None]:
    try:
        r = subprocess.run(
            ["docker", "inspect", "--format", "{{json .Mounts}}", container_id],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            return None, None
        import json
        mounts = json.loads(r.stdout)
        gguf_src = gguf_dst = first_src = first_dst = None
        for m in mounts:
            src = m.get("Source")
            dst = m.get("Destination")
            if not src or not dst:
                continue
            if first_src is None:
                first_src, first_dst = src, dst
            if "gguf" in dst.lower() or "gguf" in src.lower():
                gguf_src, gguf_dst = src, dst
        if gguf_src:
            return gguf_src, gguf_dst
        return first_src, first_dst
    except Exception:
        pass
    return None, None


def auto_discover() -> list[dict[str, Any]]:
    instances = []

    # Docker containers
    try:
        r = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=10,
        )
        for line in r.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            cid, image, cname, ports = parts[0], parts[1], parts[2], parts[3]
            is_ollama = False
            if "ollama/ollama" in image.lower():
                is_ollama = True
            elif "ollama" in image.lower() and "11434" in ports:
                is_ollama = True
            if not is_ollama:
                continue
            gguf_dir, container_gguf_dir = _detect_container_mounts(cid)
            instances.append({
                "type": "docker",
                "name": f"Docker — {cname}",
                "url": "http://localhost:11434",
                "container_id": cid,
                "api_key": None,
                "gguf_dir": gguf_dir,
                "container_gguf_dir": container_gguf_dir,
            })
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        pass

    # Local ollama
    if shutil.which("ollama"):
        instances.append({
            "type": "local",
            "name": "Local Ollama",
            "url": "http://localhost:11434",
            "container_id": None,
            "api_key": None,
            "gguf_dir": None,
        })

    return instances


def register_instance(data: dict[str, Any]) -> dict[str, Any]:
    instance_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO instances (id, name, type, url, api_key, container_id, gguf_dir, container_gguf_dir)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                instance_id,
                data["name"],
                data["type"],
                data.get("url", "http://localhost:11434"),
                data.get("api_key"),
                data.get("container_id"),
                data.get("gguf_dir"),
                data.get("container_gguf_dir"),
            ),
        )
    return get_instance(instance_id)


def get_instance(instance_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM instances WHERE id = ?", (instance_id,)
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def list_instances() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM instances ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def update_instance(instance_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    fields = []
    values = []
    for key in ("name", "type", "url", "api_key", "container_id", "gguf_dir", "container_gguf_dir"):
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return get_instance(instance_id)
    fields.append("updated_at = datetime('now')")
    with get_db() as conn:
        conn.execute(
            f"UPDATE instances SET {', '.join(fields)} WHERE id = ?",
            (*values, instance_id),
        )
    return get_instance(instance_id)


def delete_instance(instance_id: str) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM instances WHERE id = ?", (instance_id,))
        return cur.rowcount > 0


def get_client(instance_id: str) -> OllamaClient:
    inst = get_instance(instance_id)
    if inst is None:
        raise ValueError(f"Instance {instance_id} not found")
    return OllamaClient(
        inst["type"],
        url=inst["url"],
        container_id=inst["container_id"],
        api_key=inst["api_key"],
        gguf_dir=inst["gguf_dir"],
        container_gguf_dir=inst.get("container_gguf_dir"),
    )

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from backend.services.gguf_parser import read_gguf_meta


class OllamaClient:
    def __init__(
        self,
        instance_type: str,
        *,
        url: str = "http://localhost:11434",
        container_id: str | None = None,
        api_key: str | None = None,
        gguf_dir: str | None = None,
        container_gguf_dir: str | None = None,
    ) -> None:
        self.type = instance_type
        self.url = url.rstrip("/")
        self.container_id = container_id
        self.api_key = api_key
        self.gguf_dir = gguf_dir
        self.container_gguf_dir = container_gguf_dir

    # -- helpers --

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _run_ollama(self, args: list[str]) -> subprocess.CompletedProcess:
        if self.type == "docker" and self.container_id:
            cmd = ["docker", "exec", self.container_id, "ollama"] + args
        else:
            cmd = ["ollama"] + args
        try:
            return subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            binary = cmd[0]
            if binary == "ollama":
                raise RuntimeError(
                    "Ollama is not installed or not on PATH. "
                    "Install it from https://ollama.com or start the Ollama application."
                )
            raise RuntimeError(
                f"'{binary}' was not found. Make sure it is installed and on PATH."
            )

    # -- model listing --

    def list_models(self) -> list[dict[str, Any]]:
        if self.type in ("docker", "local"):
            r = self._run_ollama(["list", "--format", "json"])
            if r.returncode == 0 and r.stdout.strip():
                return self._parse_list_json(r.stdout)
            r = self._run_ollama(["list"])
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip())
            return self._parse_list_text(r.stdout)
        else:
            data = self._api_get("/api/tags")
            return data.get("models", data if isinstance(data, list) else [])

    def _parse_list_json(self, text: str) -> list[dict[str, Any]]:
        import json

        data = json.loads(text)
        models = data if isinstance(data, list) else data.get("models", [])
        result = []
        for m in models:
            details = m.get("details") or {}
            result.append({
                "name": m.get("name", ""),
                "size": m.get("size", 0),
                "modified": m.get("modified_at", ""),
                "family": details.get("family"),
                "parameter_size": details.get("parameter_size"),
                "quantization_level": details.get("quantization_level"),
            })
        return result

    def _parse_list_text(self, text: str) -> list[dict[str, Any]]:
        models = []
        for line in text.strip().split("\n")[1:]:
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            size_str = f"{parts[2]} {parts[3]}" if len(parts) > 3 else parts[2]
            modified = " ".join(parts[4:]) if len(parts) > 4 else ""
            models.append({
                "name": parts[0],
                "size": size_str,
                "modified": modified,
            })
        for m in models:
            self._enrich_model_details(m)
        return models

    def _enrich_model_details(self, model: dict[str, Any]) -> None:
        try:
            r = self._run_ollama(["show", model["name"], "--format", "json"])
            if r.returncode == 0 and r.stdout.strip():
                import json
                data = json.loads(r.stdout)
                details = data.get("details") or {}
                model["family"] = details.get("family")
                model["parameter_size"] = details.get("parameter_size")
                model["quantization_level"] = details.get("quantization_level")
                return
        except Exception:
            pass
        try:
            r = self._run_ollama(["show", model["name"]])
            if r.returncode != 0:
                return
            for line in r.stdout.split("\n"):
                line = line.strip()
                if line.startswith("architecture") and "family" not in model:
                    model["family"] = line.split(None, 1)[-1].strip()
                elif line.startswith("parameters") and "parameter_size" not in model:
                    model["parameter_size"] = line.split(None, 1)[-1].strip()
                elif line.startswith("quantization") and "quantization_level" not in model:
                    model["quantization_level"] = line.split(None, 1)[-1].strip()
        except Exception:
            pass

    # -- model inspect --

    def inspect_model(self, name: str) -> dict[str, Any]:
        if self.type in ("docker", "local"):
            r = self._run_ollama(["show", name])
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip())
            return {"modelfile": r.stdout}
        else:
            return self._api_get(f"/api/show", {"model": name})

    # -- model delete --

    def delete_model(self, name: str) -> None:
        if self.type in ("docker", "local"):
            r = self._run_ollama(["rm", name])
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip())
        else:
            self._api_delete("/api/delete", {"model": name})

    # -- pull from registry --

    def pull_model(self, name: str) -> None:
        if self.type in ("docker", "local"):
            r = self._run_ollama(["pull", name])
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip())
        else:
            self._api_post("/api/pull", {"model": name})

    # -- import GGUF --

    def import_gguf(self, gguf_path: str, model_name: str) -> None:
        if self.type == "docker" and self.container_id:
            self._docker_import(gguf_path, model_name)
        elif self.type == "local":
            self._local_import(gguf_path, model_name)
        else:
            raise RuntimeError("GGUF import only supported for local/docker instances")

    def _run_docker(self, args: list[str], **kwargs) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(["docker"] + args, **kwargs)
        except FileNotFoundError:
            raise RuntimeError(
                "Docker is not installed or not on PATH. "
                "Install Docker Desktop from https://docker.com."
            )

    def _docker_import(self, gguf_path: str, model_name: str) -> None:
        gguf_path = Path(gguf_path).resolve()
        gguf_name = gguf_path.name

        # Try shared-volume path via container_gguf_dir
        container_file = self._resolve_container_path(gguf_path)
        if container_file:
            container_dir = str(Path(container_file).parent)
            with tempfile.TemporaryDirectory() as tmpdir:
                modelfile = Path(tmpdir) / "Modelfile"
                modelfile.write_text(f"FROM {container_file}\n")
                self._run_docker(
                    ["cp", str(modelfile), f"{self.container_id}:{container_dir}/Modelfile"],
                    check=True, capture_output=True, text=True,
                )
                r = self._run_docker(
                    ["exec", self.container_id, "ollama", "create", model_name, "-f", f"{container_dir}/Modelfile"],
                    capture_output=True, text=True,
                )
                self._run_docker(
                    ["exec", self.container_id, "rm", f"{container_dir}/Modelfile"],
                    capture_output=True,
                )
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.strip())
                return

        # Fallback: docker cp the GGUF file into the container
        container_path = f"/tmp/ollama-import/{gguf_name}"
        self._run_docker(
            ["exec", self.container_id, "mkdir", "-p", "/tmp/ollama-import"],
            capture_output=True,
        )
        self._run_docker(
            ["cp", str(gguf_path), f"{self.container_id}:{container_path}"],
            check=True, capture_output=True, text=True,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            modelfile = Path(tmpdir) / "Modelfile"
            modelfile.write_text(f"FROM {container_path}\n")
            self._run_docker(
                ["cp", str(modelfile), f"{self.container_id}:/tmp/ollama-import/Modelfile"],
                check=True, capture_output=True, text=True,
            )
            r = self._run_docker(
                ["exec", self.container_id, "ollama", "create", model_name, "-f", "/tmp/ollama-import/Modelfile"],
                capture_output=True, text=True,
            )
            self._run_docker(
                ["exec", self.container_id, "rm", "-rf", "/tmp/ollama-import"],
                capture_output=True,
            )
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip())

    def _resolve_container_path(self, host_path: Path) -> str | None:
        if not self.gguf_dir or not self.container_gguf_dir:
            return None
        host_dir = Path(self.gguf_dir).resolve()
        try:
            relative = host_path.relative_to(host_dir)
        except ValueError:
            return None
        return f"{self.container_gguf_dir.rstrip('/')}/{relative}"

    def _local_import(self, gguf_path: str, model_name: str) -> None:
        gguf_path = Path(gguf_path).resolve()
        with tempfile.TemporaryDirectory() as tmpdir:
            modelfile = Path(tmpdir) / "Modelfile"
            modelfile.write_text(f"FROM {gguf_path}\n")
            try:
                r = subprocess.run(
                    ["ollama", "create", model_name, "-f", str(modelfile)],
                    capture_output=True, text=True,
                )
            except FileNotFoundError:
                raise RuntimeError(
                    "Ollama is not installed or not on PATH. "
                    "Install it from https://ollama.com or start the Ollama application."
                )
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip())

    # -- pull from HuggingFace --

    def pull_from_huggingface(self, url: str, hf_token: str | None = None) -> None:
        import httpx

        headers = {}
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"

        gguf_path = None
        try:
            with httpx.Client(follow_redirects=True, timeout=300) as client:
                resp = client.get(url, headers=headers)
                resp.raise_for_status()

                with tempfile.NamedTemporaryFile(suffix=".gguf", delete=False) as tmp:
                    tmp.write(resp.content)
                    gguf_path = tmp.name

            meta = read_gguf_meta(gguf_path)
            name = (
                meta.get("label")
                or Path(url).stem.replace(".gguf", "").lower().replace("_", "").replace("-instruct", "")
                or suggest_name(gguf_path)
            )
            self.import_gguf(gguf_path, name)
        finally:
            if gguf_path:
                Path(gguf_path).unlink(missing_ok=True)

    # -- GGUF library --

    def list_gguf_files(self) -> list[dict[str, Any]]:
        gguf_dir = self.container_gguf_dir if self.container_gguf_dir and Path(self.container_gguf_dir).is_dir() else self.gguf_dir
        if not gguf_dir or not Path(gguf_dir).is_dir():
            return []
        files = []
        for f in sorted(Path(gguf_dir).rglob("*.gguf")):
            stat = f.stat()
            meta = read_gguf_meta(f)
            files.append({
                "path": str(f),
                "name": f.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "quantization": meta.get("quantization"),
                "family": meta.get("family"),
                "parameter_size": meta.get("parameter_size"),
                "label": meta.get("label"),
                "context_length": meta.get("context_length"),
            })
        return files

    # -- HTTP API wrappers --

    def _api_get(self, path: str, params: dict | None = None) -> Any:
        with httpx.Client(base_url=self.url, headers=self._headers()) as client:
            r = client.get(path, params=params)
            r.raise_for_status()
            return r.json()

    def _api_post(self, path: str, data: dict) -> Any:
        with httpx.Client(base_url=self.url, headers=self._headers()) as client:
            r = client.post(path, json=data)
            r.raise_for_status()
            return r.json()

    def _api_delete(self, path: str, data: dict) -> Any:
        with httpx.Client(base_url=self.url, headers=self._headers()) as client:
            r = client.request("DELETE", path, json=data)
            r.raise_for_status()
            return r.json()


def suggest_name(gguf_path: str) -> str:
    name = Path(gguf_path).stem
    for prefix in [
        "google_", "microsoft_", "openai_", "meta-llama_",
        "Qwen_", "Mistral_", "Instinct_",
    ]:
        if name.startswith(prefix):
            name = name[len(prefix):]
    import re
    name = re.sub(r"-[Qq][0-9]+(_[A-Za-z0-9]+)+$", "", name)
    name = re.sub(r"-?[Mm][Xx][Ff][Pp]4$", "", name)
    name = name.lower().replace("_", "")
    return name


def name_exists(client: OllamaClient, name: str) -> bool:
    try:
        models = client.list_models()
        return any(m["name"].split(":")[0] == name for m in models)
    except RuntimeError:
        return False

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException, Request
from python_multipart.multipart import MultipartParser, parse_options_header

from backend.services.instance_manager import get_client
from backend.services.ollama_client import suggest_name
from backend.services.task_manager import start_background

router = APIRouter(prefix="/api/import", tags=["import"])

UPLOAD_DIR = Path("/unified/tmp/ollama-manager-uploads")
CHUNK_SIZE = 1024 * 1024


def _do_import(instance_id: str, gguf_path: str, model_name: str) -> None:
    client = get_client(instance_id)
    client.import_gguf(gguf_path, model_name)


@router.get("/suggest-name")
def suggest(gguf_path: str):
    return {"suggested": suggest_name(gguf_path)}


@router.post("/upload")
async def upload_gguf(request: Request):
    ct = request.headers.get("content-type", "")
    _, params = parse_options_header(ct)
    boundary = params.get(b"boundary")
    if not boundary:
        raise HTTPException(400, "Missing multipart boundary")

    instance_id = None
    model_name = None
    dest = None
    dest_file = None

    class Callbacks:
        def __init__(self):
            self._hdr_name = b""
            self._hdr_val = bytearray()
            self._disposition = b""
            self.field_name = ""
            self.field_value = bytearray()
            self.filename = ""

        def on_part_begin(self):
            self._hdr_name = b""
            self._hdr_val = bytearray()
            self._disposition = b""
            self.field_name = ""
            self.field_value = bytearray()
            self.filename = ""

        def on_header_field(self, data, start, end):
            self._hdr_name = data[start:end].lower()

        def on_header_value(self, data, start, end):
            if self._hdr_name == b"content-disposition":
                self._disposition = data[start:end]

        def on_header_end(self):
            pass

        def on_headers_finished(self):
            nonlocal instance_id, model_name, dest, dest_file
            if self._disposition:
                params = parse_options_header(self._disposition)[1]
                self.field_name = unquote(params.get(b"name", b"").decode("latin-1"))
                self.filename = params.get(b"filename", b"")
                if self.filename:
                    self.filename = unquote(self.filename.decode("latin-1"))
                    if not self.filename.lower().endswith(".gguf"):
                        raise HTTPException(400, "Only .gguf files are accepted")
                    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
                    dest = UPLOAD_DIR / self.filename
                    dest_file = open(dest, "wb")

        def on_part_data(self, data, start, end):
            chunk = data[start:end]
            if dest_file:
                dest_file.write(chunk)
            else:
                self.field_value.extend(chunk)

        def on_part_end(self):
            nonlocal instance_id, model_name
            if dest_file is None:
                val = self.field_value.decode("latin-1") if self.field_value else ""
                if self.field_name == "instance_id":
                    instance_id = val
                elif self.field_name == "model_name":
                    model_name = val

        def on_end(self):
            pass

    cbs = Callbacks()
    parser = MultipartParser(boundary, {
        "on_part_begin": cbs.on_part_begin,
        "on_header_field": cbs.on_header_field,
        "on_header_value": cbs.on_header_value,
        "on_header_end": cbs.on_header_end,
        "on_headers_finished": cbs.on_headers_finished,
        "on_part_data": cbs.on_part_data,
        "on_part_end": cbs.on_part_end,
        "on_end": cbs.on_end,
    })

    try:
        async for chunk in request.stream():
            if chunk:
                parser.write(chunk)
            else:
                parser.finalize()
    except HTTPException:
        if dest_file:
            dest_file.close()
            if dest:
                dest.unlink(missing_ok=True)
        raise
    except Exception:
        if dest_file:
            dest_file.close()
            if dest:
                dest.unlink(missing_ok=True)
        raise

    if dest_file:
        dest_file.close()

    if not instance_id:
        if dest:
            dest.unlink(missing_ok=True)
        raise HTTPException(400, "instance_id required")
    if not dest:
        raise HTTPException(400, "No file provided")

    if not model_name:
        model_name = re.sub(r'\.gguf$', '', dest.name, flags=re.I)

    try:
        task_id = start_background("import-gguf", _do_import, instance_id, str(dest), model_name)
        return {"task_id": task_id, "model": model_name}
    except Exception:
        dest.unlink(missing_ok=True)
        raise


@router.post("/from-path")
def import_from_path(instance_id: str, gguf_path: str, model_name: str):
    path = Path(gguf_path)
    if not path.exists():
        raise HTTPException(400, f"File not found: {gguf_path}")
    if path.suffix.lower() != ".gguf":
        raise HTTPException(400, "Not a .gguf file")

    task_id = start_background("import-gguf", _do_import, instance_id, str(path), model_name)
    return {"task_id": task_id, "model": model_name}

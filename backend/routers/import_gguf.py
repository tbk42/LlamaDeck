from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from backend.services.instance_manager import get_client
from backend.services.ollama_client import suggest_name
from backend.services.task_manager import start_background

router = APIRouter(prefix="/api/import", tags=["import"])

UPLOAD_DIR = Path("/tmp/ollama-manager-uploads")


def _do_import(instance_id: str, gguf_path: str, model_name: str) -> None:
    client = get_client(instance_id)
    client.import_gguf(gguf_path, model_name)


@router.get("/suggest-name")
def suggest(gguf_path: str):
    return {"suggested": suggest_name(gguf_path)}


@router.post("/upload")
async def upload_gguf(
    instance_id: str = Form(...),
    model_name: str = Form(...),
    file: UploadFile = File(...),
):
    if not file.filename or not file.filename.lower().endswith(".gguf"):
        raise HTTPException(400, "Only .gguf files are accepted")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / file.filename

    CHUNK_SIZE = 1024 * 1024
    with open(dest, "wb") as f:
        while chunk := await file.read(CHUNK_SIZE):
            f.write(chunk)

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

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.services.instance_manager import get_client
from backend.services.task_manager import start_background

router = APIRouter(prefix="/api/gguf-library", tags=["gguf-library"])


def _do_import(instance_id: str, gguf_path: str, model_name: str) -> None:
    client = get_client(instance_id)
    client.import_gguf(gguf_path, model_name)


@router.get("/{instance_id}")
def list_gguf(instance_id: str):
    try:
        client = get_client(instance_id)
        return client.list_gguf_files()
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/import")
def import_from_library(instance_id: str, gguf_path: str, model_name: str):
    task_id = start_background("import-gguf", _do_import, instance_id, gguf_path, model_name)
    return {"task_id": task_id, "model": model_name}

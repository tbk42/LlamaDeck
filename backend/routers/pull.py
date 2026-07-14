from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import ModelPull, HuggingFacePull
from backend.services.instance_manager import get_client
from backend.services.task_manager import start_background

router = APIRouter(prefix="/api/pull", tags=["pull"])


def _do_registry_pull(instance_id: str, name: str) -> None:
    client = get_client(instance_id)
    client.pull_model(name)


def _do_hf_pull(instance_id: str, url: str, hf_token: str | None) -> None:
    client = get_client(instance_id)
    client.pull_from_huggingface(url, hf_token)


@router.post("/registry")
def pull_from_registry(body: ModelPull):
    task_id = start_background(
        "pull-registry", _do_registry_pull, body.instance_id, body.name,
    )
    return {"task_id": task_id}


@router.post("/huggingface")
def pull_from_huggingface(body: HuggingFacePull):
    task_id = start_background(
        "pull-huggingface", _do_hf_pull, body.instance_id, body.url, body.hf_token,
    )
    return {"task_id": task_id}

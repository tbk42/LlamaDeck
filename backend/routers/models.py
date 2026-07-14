from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import ModelDelete, ModelInspect
from backend.services.instance_manager import get_client

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/{instance_id}")
def list_models(instance_id: str):
    try:
        client = get_client(instance_id)
        return client.list_models()
    except ValueError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.post("/inspect")
def inspect(body: ModelInspect):
    try:
        client = get_client(body.instance_id)
        return client.inspect_model(body.name)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))


@router.delete("")
def delete_model(body: ModelDelete):
    try:
        client = get_client(body.instance_id)
        client.delete_model(body.name)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except RuntimeError as e:
        raise HTTPException(502, str(e))

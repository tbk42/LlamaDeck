from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import InstanceCreate, InstanceUpdate
from backend.services import instance_manager

router = APIRouter(prefix="/api/instances", tags=["instances"])


@router.get("/discover")
def discover():
    return instance_manager.auto_discover()


@router.get("")
def list_all():
    return instance_manager.list_instances()


@router.post("")
def create(body: InstanceCreate):
    return instance_manager.register_instance(body.model_dump())


@router.get("/{instance_id}")
def get(instance_id: str):
    inst = instance_manager.get_instance(instance_id)
    if not inst:
        raise HTTPException(404, "Instance not found")
    return inst


@router.patch("/{instance_id}")
def update(instance_id: str, body: InstanceUpdate):
    inst = instance_manager.update_instance(instance_id, body.model_dump(exclude_none=True))
    if not inst:
        raise HTTPException(404, "Instance not found")
    return inst


@router.delete("/{instance_id}")
def delete(instance_id: str):
    if not instance_manager.delete_instance(instance_id):
        raise HTTPException(404, "Instance not found")
    return {"ok": True}

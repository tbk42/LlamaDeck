from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.services.task_manager import get_task

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}")
def task_status(task_id: str):
    t = get_task(task_id)
    if t is None:
        raise HTTPException(404, "Task not found")
    return t
